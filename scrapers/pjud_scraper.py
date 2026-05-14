"""
PJUD Scraper — Extrae sentencias tributarias del Poder Judicial de Chile
Fuentes:
  - Tribunales Tributarios y Aduaneros (TTA)
  - Corte de Apelaciones (materias tributarias)
  - Corte Suprema (materias tributarias)

Estrategia:
  - El buscador principal del PJUD es JS-heavy → Playwright
  - Las páginas de resultados del OJV son dinámicas
  - Búsqueda por palabras clave: "tributario", "SII", "impuesto", "renta", "IVA"
"""

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

# Términos de búsqueda tributaria para filtrar sentencias relevantes
TERMINOS_TRIBUTARIOS = [
    "tributario", "impuesto", "SII", "renta", "IVA", "aduanero",
    "contribuyente", "fiscalización", "elusión", "evasión",
    "servicio de impuestos", "código tributario",
]

# Tribunales Tributarios y Aduaneros de Chile
TTA_TRIBUNALES = {
    "1": "TTA Santiago 1° (Primera Sala)",
    "2": "TTA Santiago 2° (Segunda Sala)",
    "3": "TTA Valparaíso",
    "4": "TTA Concepción",
    "5": "TTA Antofagasta",
    "6": "TTA Temuco",
    "7": "TTA Rancagua",
    "8": "TTA Talca",
    "9": "TTA Puerto Montt",
    "10": "TTA Iquique",
    "11": "TTA Arica",
    "12": "TTA La Serena",
    "13": "TTA Chillán",
}

BASE_PJUD = "https://www.pjud.cl"
BASE_OJV = "https://oficinajudicialvirtual.pjud.cl"


@dataclass
class Sentencia:
    tribunal: str
    tipo_tribunal: str   # TTA | Corte Apelaciones | Corte Suprema
    rol: str
    fecha: str
    materia: str
    resumen: str
    url: str
    doc_id: str

    def to_dict(self) -> dict:
        return {
            "tribunal": self.tribunal,
            "tipo_tribunal": self.tipo_tribunal,
            "rol": self.rol,
            "fecha": self.fecha,
            "materia": self.materia,
            "resumen": self.resumen,
            "url": self.url,
            "doc_id": self.doc_id,
        }


class PJUDScraper:
    def __init__(self, state_manager, force: bool = False, days_lookback: int = 7):
        self.state = state_manager
        self.force = force
        self.days_lookback = days_lookback
        self.cutoff_date = datetime.now() - timedelta(days=days_lookback)

    def _is_new(self, source_key: str, doc_id: str, fecha_dt: datetime | None) -> bool:
        if self.force:
            return True
        if self.state.is_seen(source_key, doc_id):
            return False
        if fecha_dt and fecha_dt < self.cutoff_date:
            return False
        return True

    def _es_tributario(self, texto: str) -> bool:
        texto_lower = texto.lower()
        return any(t.lower() in texto_lower for t in TERMINOS_TRIBUTARIOS)

    # ── PLAYWRIGHT — Buscador PJUD ────────────────────────────────────────────

    def _scrape_con_playwright(self) -> list[dict]:
        """
        Usa Playwright para navegar el buscador de jurisprudencia del PJUD.
        URL: https://buscador.pjud.cl/
        """
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            log.warning("  ⚠️ Playwright no instalado. Ejecutar: pip install playwright && playwright install chromium")
            return self._scrape_tta_fallback()

        items = []
        terminos_busqueda = ["tributario IVA", "impuesto renta SII", "código tributario"]

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = browser.new_context(
                    locale="es-CL",
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0.0.0 Safari/537.36",
                )
                page = context.new_page()

                for termino in terminos_busqueda:
                    log.info(f"    Buscando en PJUD: '{termino}'")
                    try:
                        nuevos = self._buscar_termino_pjud(page, termino)
                        items.extend(nuevos)
                        time.sleep(3)
                    except PWTimeout:
                        log.warning(f"    Timeout buscando '{termino}'")
                    except Exception as e:
                        log.error(f"    Error buscando '{termino}': {e}")

                # Buscar específicamente en TTA
                tta_items = self._buscar_tta_playwright(page)
                items.extend(tta_items)

                browser.close()

        except Exception as e:
            log.error(f"  Error general Playwright: {e}")
            return self._scrape_tta_fallback()

        # Deduplicar
        seen_ids = set()
        unique_items = []
        for item in items:
            if item["doc_id"] not in seen_ids:
                seen_ids.add(item["doc_id"])
                unique_items.append(item)

        return unique_items

    def _buscar_termino_pjud(self, page, termino: str) -> list[dict]:
        """Navega el buscador de jurisprudencia y extrae resultados."""
        items = []

        try:
            page.goto("https://buscador.pjud.cl/buscador/", timeout=30000, wait_until="networkidle")
            time.sleep(2)

            # Buscar campo de búsqueda
            search_input = page.query_selector("input[type='text'], input[type='search'], #busqueda, .search-input")
            if not search_input:
                search_input = page.query_selector("input")

            if search_input:
                search_input.fill(termino)
                search_input.press("Enter")
                time.sleep(3)
                page.wait_for_load_state("networkidle", timeout=15000)

            # Extraer resultados
            html = page.content()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")

            # Buscar filas/cards de resultados
            resultados = soup.find_all(["tr", "div", "article"],
                                       class_=re.compile(r"resultado|sentencia|row|item", re.I))

            for res in resultados[:20]:
                texto = res.get_text(" ", strip=True)
                if not self._es_tributario(texto):
                    continue

                link = res.find("a")
                href = ""
                if link:
                    href = link.get("href", "")
                    if href and not href.startswith("http"):
                        href = "https://buscador.pjud.cl" + href

                # Extraer rol/fecha/tribunal del texto
                rol = re.search(r"[CRTO]-\d+-\d+|\d{4}-\d+", texto)
                rol_str = rol.group(0) if rol else texto[:30]

                fecha = re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", texto)
                fecha_str = fecha.group(0) if fecha else datetime.now().strftime("%d-%m-%Y")

                doc_id = f"pjud_busq_{rol_str}_{fecha_str}"

                if self._is_new("pjud_buscador", doc_id, None):
                    items.append(Sentencia(
                        tribunal="PJUD",
                        tipo_tribunal="Jurisprudencia",
                        rol=rol_str,
                        fecha=fecha_str,
                        materia=texto[:200],
                        resumen=texto[:500],
                        url=href or "https://buscador.pjud.cl/",
                        doc_id=doc_id,
                    ).to_dict())
                    self.state.mark_seen("pjud_buscador", doc_id)

        except Exception as e:
            log.error(f"  Error en búsqueda '{termino}': {e}")

        return items

    def _buscar_tta_playwright(self, page) -> list[dict]:
        """
        Navega directamente a la sección TTA del PJUD/OJV.
        Los TTA publican sus sentencias en el OJV.
        """
        items = []

        try:
            # Intentar acceder a las causas de TTA via OJV
            page.goto(f"{BASE_OJV}/homeAplicacion.php", timeout=30000, wait_until="networkidle")
            time.sleep(2)

            # Buscar sección de tribunales especiales
            html = page.content()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")

            # Extraer links de TTA
            for link in soup.find_all("a", href=True):
                texto = link.get_text(strip=True)
                if "tributario" in texto.lower() or "aduanero" in texto.lower():
                    href = link.get("href", "")
                    log.info(f"    Encontrado link TTA: {texto} → {href}")

        except Exception as e:
            log.debug(f"  OJV no accesible: {e}")

        return items

    # ── FALLBACK: Scraping HTML directo ──────────────────────────────────────

    def _scrape_tta_fallback(self) -> list[dict]:
        """
        Fallback cuando Playwright no está disponible.
        Intenta acceder a las páginas HTML estáticas del PJUD.
        """
        import httpx
        from bs4 import BeautifulSoup

        log.info("  Usando fallback HTML para PJUD...")
        items = []

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0 Safari/537.36",
            "Accept-Language": "es-CL,es;q=0.9",
        }

        # URLs de secciones públicas PJUD con jurisprudencia
        urls_fallback = [
            f"{BASE_PJUD}/tribunales/tipo/3",      # Tribunales tributarios
            f"{BASE_PJUD}/jurisprudencia",          # Jurisprudencia general
        ]

        try:
            with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
                for url in urls_fallback:
                    try:
                        resp = client.get(url)
                        resp.raise_for_status()
                        soup = BeautifulSoup(resp.text, "lxml")

                        # Buscar links con términos tributarios
                        for link in soup.find_all("a", href=True):
                            texto = link.get_text(strip=True)
                            if self._es_tributario(texto) and len(texto) > 10:
                                href = link.get("href", "")
                                if href and not href.startswith("http"):
                                    href = BASE_PJUD + href

                                doc_id = f"pjud_html_{texto[:30].replace(' ', '_')}"
                                if self._is_new("pjud_fallback", doc_id, None):
                                    items.append(Sentencia(
                                        tribunal="PJUD",
                                        tipo_tribunal="Jurisprudencia",
                                        rol="Ver link",
                                        fecha=datetime.now().strftime("%d-%m-%Y"),
                                        materia=texto,
                                        resumen=texto,
                                        url=href,
                                        doc_id=doc_id,
                                    ).to_dict())
                                    self.state.mark_seen("pjud_fallback", doc_id)

                        time.sleep(2)
                    except Exception as e:
                        log.error(f"  Error accediendo {url}: {e}")

        except Exception as e:
            log.error(f"  Error fallback PJUD: {e}")

        return items

    # ── SCRAPER CORTE SUPREMA ─────────────────────────────────────────────────

    def _scrape_corte_suprema(self) -> list[dict]:
        """
        La Corte Suprema publica algunas sentencias en formato HTML accesible.
        Filtra las relacionadas con materias tributarias.
        """
        import httpx
        from bs4 import BeautifulSoup

        items = []
        headers = {"User-Agent": "Mozilla/5.0 Chrome/124.0 Safari/537.36"}

        # El PJUD tiene un buscador de jurisprudencia de la CS
        url = f"{BASE_PJUD}/jurisprudencia-destacada"

        try:
            with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code != 200:
                    return items

                soup = BeautifulSoup(resp.text, "lxml")
                articulos = soup.find_all(["article", "div"], class_=re.compile(r"card|post|item|sentencia", re.I))

                for art in articulos[:30]:
                    texto = art.get_text(" ", strip=True)
                    if not self._es_tributario(texto):
                        continue

                    link = art.find("a")
                    href = ""
                    if link:
                        href = link.get("href", "")
                        if href and not href.startswith("http"):
                            href = BASE_PJUD + href

                    titulo = ""
                    h_tag = art.find(["h1", "h2", "h3", "h4"])
                    if h_tag:
                        titulo = h_tag.get_text(strip=True)

                    fecha = re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", texto)
                    fecha_str = fecha.group(0) if fecha else datetime.now().strftime("%d-%m-%Y")

                    doc_id = f"cs_{titulo[:30].replace(' ', '_')}_{fecha_str}"

                    if self._is_new("corte_suprema", doc_id, None):
                        items.append(Sentencia(
                            tribunal="Corte Suprema",
                            tipo_tribunal="Corte Suprema",
                            rol=re.search(r"[CRTO]-\d+-\d+|\d{4}-\d+", texto) and
                                re.search(r"[CRTO]-\d+-\d+|\d{4}-\d+", texto).group(0) or "Ver link",
                            fecha=fecha_str,
                            materia=titulo or texto[:100],
                            resumen=texto[:500],
                            url=href or url,
                            doc_id=doc_id,
                        ).to_dict())
                        self.state.mark_seen("corte_suprema", doc_id)

        except Exception as e:
            log.error(f"  Error Corte Suprema: {e}")

        return items

    # ── ORQUESTADOR ──────────────────────────────────────────────────────────

    def scrape_all(self) -> dict[str, list[dict]]:
        result = {}

        # TTA y buscador general
        log.info("  Scraping TTA y buscador PJUD...")
        tta_items = self._scrape_con_playwright()
        if tta_items:
            result["tta_sentencias"] = tta_items

        time.sleep(2)

        # Corte Suprema
        log.info("  Scraping Corte Suprema (jurisprudencia tributaria)...")
        cs_items = self._scrape_corte_suprema()
        if cs_items:
            result["corte_suprema"] = cs_items

        return result
