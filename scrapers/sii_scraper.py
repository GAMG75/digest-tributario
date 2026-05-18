"""
SII Scraper — Extrae novedades de www.sii.cl
Secciones monitoreadas:
  - Circulares
  - Resoluciones
  - Jurisprudencia Administrativa (Oficios)
"""

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = "https://www.sii.cl"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-CL,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Meses en español para parsear fechas del SII
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

URLS_SII = {
    "circulares": f"{BASE_URL}/normativa_legislacion/circulares/2025/indcir2025.htm",
    "resoluciones": f"{BASE_URL}/normativa_legislacion/resoluciones/2025/res_ind2025.htm",
    "jurisprudencia": f"{BASE_URL}/normativa_legislacion/jurisprudencia_administrativa/2025/index.html",
}


@dataclass
class SIIDocumento:
    tipo: str          # circular | resolución | oficio
    numero: str
    fecha: str
    materia: str
    url: str
    doc_id: str        # ID único para deduplicación

    def to_dict(self) -> dict:
        return {
            "tipo": self.tipo,
            "numero": self.numero,
            "fecha": self.fecha,
            "materia": self.materia,
            "url": self.url,
            "doc_id": self.doc_id,
        }


class SIIScraper:
    def __init__(self, state_manager, force: bool = False, days_lookback: int = 7):
        self.state = state_manager
        self.force = force
        self.days_lookback = days_lookback
        self.cutoff_date = datetime.now() - timedelta(days=days_lookback)
        self.client = httpx.Client(
            headers=HEADERS,
            timeout=30,
            follow_redirects=True,
            verify=True,
        )

    def _get(self, url: str) -> BeautifulSoup | None:
        try:
            resp = self.client.get(url)
            resp.raise_for_status()
            resp.encoding = resp.encoding or "utf-8"
            return BeautifulSoup(resp.text, "lxml")
        except httpx.HTTPStatusError as e:
            log.error(f"HTTP {e.response.status_code} al acceder {url}")
        except Exception as e:
            log.error(f"Error accediendo {url}: {e}")
        return None

    def _parse_fecha_sii(self, texto: str) -> datetime | None:
        """Parsea fechas en formato del SII: '15-01-2025' o '15 de enero de 2025'."""
        texto = texto.strip().lower()
        # Formato DD-MM-YYYY o DD/MM/YYYY
        m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", texto)
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass
        # Formato "15 de enero de 2025"
        m = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", texto)
        if m:
            mes = MESES.get(m.group(2), 0)
            if mes:
                try:
                    return datetime(int(m.group(3)), mes, int(m.group(1)))
                except ValueError:
                    pass
        # Solo año: 2025
        m = re.search(r"(\d{4})", texto)
        if m and int(m.group(1)) >= 2020:
            return datetime(int(m.group(1)), 1, 1)
        return None

    def _is_new(self, source_key: str, doc_id: str, fecha_dt: datetime | None) -> bool:
        """Determina si un documento es nuevo (no visto y dentro del período)."""
        if self.force:
            return True
        if self.state.is_seen(source_key, doc_id):
            return False
        if fecha_dt and fecha_dt < self.cutoff_date:
            return False
        return True

    # ── CIRCULARES ───────────────────────────────────────────────────────────

    def scrape_circulares(self) -> list[dict]:
        log.info("  Scraping circulares SII...")
        soup = self._get(URLS_SII["circulares"])
        if not soup:
            return []

        items = []
        # El SII presenta circulares en tablas con columnas: N°, Fecha, Materia
        tablas = soup.find_all("table")

        for tabla in tablas:
            filas = tabla.find_all("tr")
            for fila in filas[1:]:  # Skip header
                celdas = fila.find_all("td")
                if len(celdas) < 2:
                    continue

                # Extraer número y link
                num_celda = celdas[0]
                link = num_celda.find("a")
                numero = num_celda.get_text(strip=True)
                href = link.get("href", "") if link else ""
                if href and not href.startswith("http"):
                    href = BASE_URL + "/" + href.lstrip("/")

                # Extraer fecha
                fecha_txt = celdas[1].get_text(strip=True) if len(celdas) > 1 else ""
                fecha_dt = self._parse_fecha_sii(fecha_txt)

                # Extraer materia
                materia_txt = celdas[2].get_text(strip=True) if len(celdas) > 2 else ""
                if not materia_txt and link:
                    materia_txt = link.get_text(strip=True)

                if not numero or numero.lower() in ("n°", "número", "numero", ""):
                    continue

                doc_id = f"circ_{numero}_{fecha_txt}"

                if self._is_new("circulares", doc_id, fecha_dt):
                    doc = SIIDocumento(
                        tipo="Circular",
                        numero=numero,
                        fecha=fecha_txt or "Sin fecha",
                        materia=materia_txt or "Ver documento",
                        url=href or URLS_SII["circulares"],
                        doc_id=doc_id,
                    )
                    items.append(doc.to_dict())
                    self.state.mark_seen("circulares", doc_id)

        log.info(f"    → {len(items)} circular(es) nueva(s)")
        return items

    # ── RESOLUCIONES ─────────────────────────────────────────────────────────

    def scrape_resoluciones(self) -> list[dict]:
        log.info("  Scraping resoluciones SII...")
        soup = self._get(URLS_SII["resoluciones"])
        if not soup:
            return []

        items = []
        tablas = soup.find_all("table")

        for tabla in tablas:
            filas = tabla.find_all("tr")
            for fila in filas[1:]:
                celdas = fila.find_all("td")
                if len(celdas) < 2:
                    continue

                num_celda = celdas[0]
                link = num_celda.find("a")
                numero = num_celda.get_text(strip=True)
                href = link.get("href", "") if link else ""
                if href and not href.startswith("http"):
                    href = BASE_URL + "/" + href.lstrip("/")

                fecha_txt = celdas[1].get_text(strip=True) if len(celdas) > 1 else ""
                fecha_dt = self._parse_fecha_sii(fecha_txt)
                materia_txt = celdas[2].get_text(strip=True) if len(celdas) > 2 else ""

                if not numero or numero.lower() in ("n°", "número", "numero", "exenta", ""):
                    continue

                doc_id = f"res_{numero}_{fecha_txt}"

                if self._is_new("resoluciones", doc_id, fecha_dt):
                    doc = SIIDocumento(
                        tipo="Resolución",
                        numero=numero,
                        fecha=fecha_txt or "Sin fecha",
                        materia=materia_txt or "Ver documento",
                        url=href or URLS_SII["resoluciones"],
                        doc_id=doc_id,
                    )
                    items.append(doc.to_dict())
                    self.state.mark_seen("resoluciones", doc_id)

        log.info(f"    → {len(items)} resolución(es) nueva(s)")
        return items

    # ── JURISPRUDENCIA / OFICIOS ─────────────────────────────────────────────

    def scrape_jurisprudencia(self) -> list[dict]:
        """
        Extrae Oficios y Jurisprudencia Administrativa del SII.
        El SII organiza esto por año → subdirectorios.
        """
        log.info("  Scraping jurisprudencia/oficios SII...")
        soup = self._get(URLS_SII["jurisprudencia"])
        if not soup:
            return []

        items = []
        anio_actual = datetime.now().year

        # Buscar link del año actual para obtener los oficios recientes
        links_anio = soup.find_all("a", href=re.compile(str(anio_actual)))
        if not links_anio:
            # Buscar todos los links de años
            links_anio = soup.find_all("a", href=re.compile(r"\d{4}"))

        urls_a_revisar = []
        for link in links_anio[:3]:  # Máximo 3 años recientes
            href = link.get("href", "")
            if href and not href.startswith("http"):
                href = BASE_URL + "/" + href.lstrip("/")
            urls_a_revisar.append(href)

        if not urls_a_revisar:
            urls_a_revisar = [URLS_SII["jurisprudencia"]]

        for url_anio in urls_a_revisar:
            time.sleep(1)
            soup_anio = self._get(url_anio)
            if not soup_anio:
                continue

            # Cada oficio/resolución es un link en la página
            for link in soup_anio.find_all("a", href=True):
                texto = link.get_text(strip=True)
                href = link.get("href", "")

                # Filtrar links relevantes (oficios típicamente tienen número)
                if not texto or len(texto) < 5:
                    continue
                if not re.search(r"\d", texto):
                    continue

                if href and not href.startswith("http"):
                    href = BASE_URL + "/" + href.lstrip("/")

                # Extraer número y fecha del texto del link
                numero = re.search(r"(\d{3,6})", texto)
                numero_str = numero.group(1) if numero else texto[:20]

                fecha_dt = self._parse_fecha_sii(texto)
                fecha_txt = fecha_dt.strftime("%d-%m-%Y") if fecha_dt else str(anio_actual)

                doc_id = f"oficio_{numero_str}_{fecha_txt}"

                if self._is_new("jurisprudencia", doc_id, fecha_dt):
                    doc = SIIDocumento(
                        tipo="Oficio/Jurisprudencia",
                        numero=numero_str,
                        fecha=fecha_txt,
                        materia=texto,
                        url=href or url_anio,
                        doc_id=doc_id,
                    )
                    items.append(doc.to_dict())
                    self.state.mark_seen("jurisprudencia", doc_id)

        log.info(f"    → {len(items)} oficio(s)/jurisprudencia nueva(s)")
        return items

    # ── ORQUESTADOR ──────────────────────────────────────────────────────────

    def scrape_all(self) -> dict[str, list[dict]]:
        result = {}
        try:
            circulares = self.scrape_circulares()
            if circulares:
                result["circulares"] = circulares
            time.sleep(2)

            resoluciones = self.scrape_resoluciones()
            if resoluciones:
                result["resoluciones"] = resoluciones
            time.sleep(2)

            jurisprudencia = self.scrape_jurisprudencia()
            if jurisprudencia:
                result["jurisprudencia"] = jurisprudencia

        finally:
            self.client.close()

        return result
