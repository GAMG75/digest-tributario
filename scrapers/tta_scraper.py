"""
TTA Scraper — Extrae sentencias y resoluciones de www.tta.cl
Tribunales Tributarios y Aduaneros de Chile
 
Secciones monitoreadas:
  - Sentencias definitivas por tribunal
  - Resoluciones interlocutorias relevantes
  - Jurisprudencia publicada
 
Los TTA publican sus resoluciones en el sitio www.tta.cl organizado
por tribunal y tipo de documento. El sitio puede tener partes estáticas
y partes dinámicas — se usa Playwright con fallback a httpx.
"""
 
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
 
import httpx
from bs4 import BeautifulSoup
 
log = logging.getLogger(__name__)
 
BASE_URL = "https://www.tta.cl"
 
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-CL,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.tta.cl/",
}
 
# Tribunales Tributarios y Aduaneros de Chile con sus identificadores
TRIBUNALES_TTA = [
    {"id": "santiago_1",    "nombre": "TTA 1° Santiago",     "region": "Metropolitana"},
    {"id": "santiago_2",    "nombre": "TTA 2° Santiago",     "region": "Metropolitana"},
    {"id": "valparaiso",    "nombre": "TTA Valparaíso",      "region": "Valparaíso"},
    {"id": "concepcion",    "nombre": "TTA Concepción",      "region": "Biobío"},
    {"id": "antofagasta",   "nombre": "TTA Antofagasta",     "region": "Antofagasta"},
    {"id": "temuco",        "nombre": "TTA Temuco",          "region": "Araucanía"},
    {"id": "rancagua",      "nombre": "TTA Rancagua",        "region": "O'Higgins"},
    {"id": "talca",         "nombre": "TTA Talca",           "region": "Maule"},
    {"id": "puerto_montt",  "nombre": "TTA Puerto Montt",    "region": "Los Lagos"},
    {"id": "iquique",       "nombre": "TTA Iquique",         "region": "Tarapacá"},
    {"id": "arica",         "nombre": "TTA Arica",           "region": "Arica y Parinacota"},
    {"id": "la_serena",     "nombre": "TTA La Serena",       "region": "Coquimbo"},
    {"id": "chillan",       "nombre": "TTA Chillán",         "region": "Ñuble"},
    {"id": "coyhaique",     "nombre": "TTA Coyhaique",       "region": "Aysén"},
    {"id": "punta_arenas",  "nombre": "TTA Punta Arenas",    "region": "Magallanes"},
]
 
# Materias tributarias clave para filtrar sentencias relevantes
MATERIAS_TRIBUTARIAS = [
    "impuesto", "tributario", "SII", "renta", "IVA", "contribuyente",
    "fiscalización", "liquidación", "giro", "resolución", "elusión",
    "evasión", "timbre", "estampillas", "global complementario",
    "primera categoría", "segunda categoría", "adicional", "aduanero",
    "aduana", "internación", "exportación", "código tributario",
    "artículo 19", "reclamación tributaria", "reclamante", "SNA",
]
 
# Tipos de documentos a monitorear en TTA
TIPOS_DOCUMENTOS = ["sentencia", "resolución", "auto", "interlocutoria"]
 
 
@dataclass
class DocumentoTTA:
    tribunal: str
    region: str
    tipo: str           # sentencia | resolución | auto
    rol: str            # ej: TT-1-2024
    fecha: str
    materia: str
    resultado: str      # acoge | rechaza | parcial (si se puede extraer)
    url: str
    doc_id: str
 
    def to_dict(self) -> dict:
        return {
            "tribunal": self.tribunal,
            "region": self.region,
            "tipo": self.tipo,
            "rol": self.rol,
            "fecha": self.fecha,
            "materia": self.materia,
            "resultado": self.resultado,
            "url": self.url,
            "doc_id": self.doc_id,
        }
 
 
class TTAScraper:
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
            encoding = resp.encoding or "utf-8"
            return BeautifulSoup(resp.content.decode(encoding, errors="replace"), "lxml")
        except httpx.HTTPStatusError as e:
            log.error(f"  HTTP {e.response.status_code}: {url}")
        except Exception as e:
            log.error(f"  Error GET {url}: {e}")
        return None
 
    def _parse_fecha(self, texto: str) -> datetime | None:
        texto = texto.strip().lower()
        meses = {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
            "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
            "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
        }
        # DD-MM-YYYY o DD/MM/YYYY
        m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", texto)
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass
        # DD de mes de YYYY
        m = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", texto)
        if m:
            mes = meses.get(m.group(2), 0)
            if mes:
                try:
                    return datetime(int(m.group(3)), mes, int(m.group(1)))
                except ValueError:
                    pass
        # YYYY-MM-DD (ISO)
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
        if m:
            try:
                return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        return None
 
    def _is_new(self, source_key: str, doc_id: str, fecha_dt: datetime | None) -> bool:
        if self.force:
            return True
        if self.state.is_seen(source_key, doc_id):
            return False
        if fecha_dt and fecha_dt < self.cutoff_date:
            return False
        return True
 
    # Palabras que indican links de navegación a descartar
    NAVIGATION_NOISE = [
        "read more", "love", "noticias", "admln", "home", "inicio",
        "contacto", "quiénes somos", "quienes somos", "fallos relevantes",
        "sentencias definitivas", "jurisprudencia", "mapa del sitio",
        "política de privacidad", "accesibilidad", "ver más", "ver mas",
    ]
 
    def _es_sentencia_real(self, texto: str) -> bool:
        """Filtra links de navegación y conserva solo sentencias reales."""
        texto_lower = texto.lower().strip()
 
        # Descartar si es muy corto
        if len(texto_lower) < 15:
            return False
 
        # Descartar links de navegación conocidos
        if any(noise in texto_lower for noise in self.NAVIGATION_NOISE):
            return False
 
        # Descartar si empieza con "love" seguido de número
        if re.match(r"love\d+", texto_lower):
            return False
 
        # Conservar si menciona "con SII" o "con Servicio" (formato típico de causas TTA)
        if "con sii" in texto_lower or "con servicio de impuestos" in texto_lower:
            return True
 
        # Conservar si tiene nombre de tribunal TTA
        if any(t["nombre"].lower() in texto_lower for t in TRIBUNALES_TTA):
            return True
 
        # Conservar si tiene rol en formato TTA
        if re.search(r"[A-Z]{2}-\d+-\d+|\d{4}-\d+", texto):
            return True
 
        return False
 
    def _extraer_resultado(self, texto: str) -> str:
        """Intenta determinar si la sentencia acoge o rechaza la reclamación."""
        texto_lower = texto.lower()
        if any(w in texto_lower for w in ["se acoge", "acoge el reclamo", "acoge la reclamación"]):
            return "✅ Acoge"
        if any(w in texto_lower for w in ["se rechaza", "rechaza el reclamo", "rechaza la reclamación"]):
            return "❌ Rechaza"
        if any(w in texto_lower for w in ["parcialmente", "en parte", "acoge en parte"]):
            return "⚠️ Parcial"
        return "—"
 
    # ── SCRAPING PRINCIPAL www.tta.cl ────────────────────────────────────────
 
    def scrape_home(self) -> list[dict]:
        """
        Extrae los documentos más recientes desde la página principal de TTA.
        Busca listas de sentencias, noticias y publicaciones recientes.
        """
        log.info("  Scraping página principal www.tta.cl...")
        items = []
 
        soup = self._get(BASE_URL)
        if not soup:
            return items
 
        # 1. Buscar sección de sentencias/resoluciones recientes
        # El TTA típicamente tiene una sección de "últimas sentencias" o similar
        for section_keyword in ["sentencia", "resolución", "fallo", "jurisprudencia", "publicación"]:
            secciones = soup.find_all(
                ["section", "div", "article"],
                class_=re.compile(section_keyword, re.I)
            )
            secciones += soup.find_all(
                ["h2", "h3", "h4"],
                string=re.compile(section_keyword, re.I)
            )
 
            for sec in secciones:
                # Si es un heading, buscar el contenedor padre
                if sec.name in ["h2", "h3", "h4"]:
                    sec = sec.parent
 
                for link in sec.find_all("a", href=True):
                    texto = link.get_text(strip=True)
                    href = link.get("href", "")
                    if not href.startswith("http"):
                        href = BASE_URL + "/" + href.lstrip("/")
 
                    if len(texto) < 5:
                        continue
                    if not self._es_sentencia_real(texto):
                        continue
                    fecha_dt = self._parse_fecha(contexto)
                    fecha_str = fecha_dt.strftime("%d-%m-%Y") if fecha_dt else datetime.now().strftime("%d-%m-%Y")
 
                    doc_id = f"tta_home_{texto[:40].replace(' ', '_')}_{fecha_str}"
 
                    if self._is_new("tta_home", doc_id, fecha_dt):
                        tipo = next((t for t in TIPOS_DOCUMENTOS if t in texto.lower()), "documento")
                        items.append(DocumentoTTA(
                            tribunal="TTA",
                            region="Chile",
                            tipo=tipo.capitalize(),
                            rol=re.search(r"[A-Z]{2}-\d+-\d+|\d{4}-\d+", texto) and
                                re.search(r"[A-Z]{2}-\d+-\d+|\d{4}-\d+", texto).group(0) or "Ver link",
                            fecha=fecha_str,
                            materia=texto[:200],
                            resultado=self._extraer_resultado(texto),
                            url=href,
                            doc_id=doc_id,
                        ).to_dict())
                        self.state.mark_seen("tta_home", doc_id)
 
        log.info(f"    → {len(items)} documento(s) desde página principal")
        return items
 
    def scrape_sentencias_por_tribunal(self) -> list[dict]:
        """
        Navega las secciones de sentencias de cada tribunal.
        Intenta las rutas más comunes que usa el sitio TTA.
        """
        log.info("  Scraping secciones de sentencias por tribunal...")
        items = []
 
        # Rutas comunes en el sitio TTA para sentencias
        rutas_candidatas = [
            "/sentencias",
            "/jurisprudencia",
            "/fallos",
            "/resoluciones",
            "/publicaciones/sentencias",
            "/publicaciones/resoluciones",
        ]
 
        for ruta in rutas_candidatas:
            url = BASE_URL + ruta
            soup = self._get(url)
            if not soup:
                time.sleep(1)
                continue
 
            # Verificar que la página tiene contenido relevante
            texto_pagina = soup.get_text(" ", strip=True).lower()
            if not any(t in texto_pagina for t in ["sentencia", "resolución", "fallo", "tributario"]):
                continue
 
            log.info(f"    Procesando: {url}")
 
            # Extraer tabla si existe
            tablas = soup.find_all("table")
            for tabla in tablas:
                filas = tabla.find_all("tr")
                for fila in filas[1:]:  # skip header
                    celdas = fila.find_all(["td", "th"])
                    if len(celdas) < 2:
                        continue
 
                    texto_fila = fila.get_text(" ", strip=True)
                    if not self._es_relevante(texto_fila) and "sentencia" not in texto_fila.lower():
                        continue
 
                    link = fila.find("a")
                    href = ""
                    if link:
                        href = link.get("href", "")
                        if href and not href.startswith("http"):
                            href = BASE_URL + "/" + href.lstrip("/")
 
                    # Intentar extraer campos estructurados
                    rol = ""
                    fecha_str = ""
                    materia = ""
 
                    for celda in celdas:
                        txt = celda.get_text(strip=True)
                        if re.match(r"[A-Z]{1,3}-\d+-\d+|\d{4}-\d+", txt):
                            rol = txt
                        elif re.search(r"\d{1,2}[-/]\d{1,2}[-/]\d{4}", txt):
                            fecha_str = txt
                        elif len(txt) > 10 and not rol and not re.search(r"^\d+$", txt):
                            materia = txt
 
                    if not rol and link:
                        rol = link.get_text(strip=True)[:30]
 
                    fecha_dt = self._parse_fecha(fecha_str) if fecha_str else None
                    if not fecha_str:
                        fecha_str = datetime.now().strftime("%d-%m-%Y")
 
                    # Detectar tribunal desde el contexto
                    tribunal_nombre = "TTA"
                    for trib in TRIBUNALES_TTA:
                        if trib["nombre"].lower() in texto_fila.lower() or \
                           trib["region"].lower() in texto_fila.lower():
                            tribunal_nombre = trib["nombre"]
                            break
 
                    doc_id = f"tta_tabla_{rol}_{fecha_str}".replace(" ", "_")
 
                    if self._is_new("tta_tablas", doc_id, fecha_dt):
                        items.append(DocumentoTTA(
                            tribunal=tribunal_nombre,
                            region="Chile",
                            tipo="Sentencia",
                            rol=rol or "Sin rol",
                            fecha=fecha_str,
                            materia=materia or texto_fila[:150],
                            resultado=self._extraer_resultado(texto_fila),
                            url=href or url,
                            doc_id=doc_id,
                        ).to_dict())
                        self.state.mark_seen("tta_tablas", doc_id)
 
            # Extraer links directos si no hay tabla
            if not tablas:
                for link in soup.find_all("a", href=True):
                    texto = link.get_text(strip=True)
                    if len(texto) < 5:
                        continue
                    if not any(t in texto.lower() for t in ["sentencia", "resolución", "fallo", "tt-", "rdo-"]):
                        continue
 
                    href = link.get("href", "")
                    if href and not href.startswith("http"):
                        href = BASE_URL + "/" + href.lstrip("/")
 
                    contexto = link.parent.get_text(" ", strip=True) if link.parent else texto
                    fecha_dt = self._parse_fecha(contexto)
                    fecha_str = fecha_dt.strftime("%d-%m-%Y") if fecha_dt else datetime.now().strftime("%d-%m-%Y")
 
                    doc_id = f"tta_link_{texto[:30].replace(' ', '_')}_{fecha_str}"
 
                    if self._is_new("tta_links", doc_id, fecha_dt):
                        items.append(DocumentoTTA(
                            tribunal="TTA",
                            region="Chile",
                            tipo="Sentencia",
                            rol=re.search(r"[A-Z]{2}-\d+-\d+|\d{4}-\d+", texto) and
                                re.search(r"[A-Z]{2}-\d+-\d+|\d{4}-\d+", texto).group(0) or texto[:25],
                            fecha=fecha_str,
                            materia=texto[:200],
                            resultado=self._extraer_resultado(contexto),
                            url=href,
                            doc_id=doc_id,
                        ).to_dict())
                        self.state.mark_seen("tta_links", doc_id)
 
            time.sleep(2)
 
        log.info(f"    → {len(items)} sentencia(s) desde secciones de tribunales")
        return items
 
    def scrape_con_playwright(self) -> list[dict]:
        """
        Usa Playwright si el sitio TTA requiere JavaScript para renderizar contenido.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            log.info("  Playwright no disponible para TTA — usando solo HTTP")
            return []
 
        items = []
        log.info("  Scraping TTA con Playwright (JS rendering)...")
 
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                page = browser.new_page(
                    locale="es-CL",
                    user_agent=HEADERS["User-Agent"],
                )
 
                # Navegar al sitio TTA
                page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
                time.sleep(2)
 
                # Buscar y hacer clic en secciones de sentencias/jurisprudencia
                nav_links = page.query_selector_all("nav a, .menu a, header a")
                urls_sentencias = set()
 
                for nav_link in nav_links:
                    texto = nav_link.inner_text().lower().strip()
                    if any(k in texto for k in ["sentencia", "jurisprudencia", "fallo", "resolución", "publicación"]):
                        href = nav_link.get_attribute("href") or ""
                        if href:
                            if not href.startswith("http"):
                                href = BASE_URL + "/" + href.lstrip("/")
                            urls_sentencias.add(href)
                            log.info(f"    Encontrada sección: {texto} → {href}")
 
                # Procesar cada sección encontrada
                for url_sec in list(urls_sentencias)[:5]:
                    try:
                        page.goto(url_sec, wait_until="networkidle", timeout=20000)
                        time.sleep(2)
                        html = page.content()
                        soup = BeautifulSoup(html, "lxml")
 
                        # Extraer documentos de la página cargada
                        for link in soup.find_all("a", href=True):
                            texto = link.get_text(strip=True)
                            href = link.get("href", "")
 
                            if len(texto) < 5:
                                continue
                            if not any(t in texto.lower() for t in
                                       ["sentencia", "resolución", "tt-", "rol", "fallo"]):
                                continue
 
                            if href and not href.startswith("http"):
                                href = BASE_URL + "/" + href.lstrip("/")
 
                            contexto = link.parent.get_text(" ", strip=True) if link.parent else texto
                            fecha_dt = self._parse_fecha(contexto)
                            fecha_str = fecha_dt.strftime("%d-%m-%Y") if fecha_dt else \
                                        datetime.now().strftime("%d-%m-%Y")
 
                            doc_id = f"tta_pw_{texto[:30].replace(' ', '_')}_{fecha_str}"
 
                            if self._is_new("tta_playwright", doc_id, fecha_dt):
                                items.append(DocumentoTTA(
                                    tribunal="TTA",
                                    region="Chile",
                                    tipo="Sentencia",
                                    rol=re.search(r"[A-Z]{2}-\d+-\d+|\d{4}-\d+", texto) and
                                        re.search(r"[A-Z]{2}-\d+-\d+|\d{4}-\d+", texto).group(0) or texto[:25],
                                    fecha=fecha_str,
                                    materia=texto[:200],
                                    resultado=self._extraer_resultado(contexto),
                                    url=href or url_sec,
                                    doc_id=doc_id,
                                ).to_dict())
                                self.state.mark_seen("tta_playwright", doc_id)
 
                    except Exception as e:
                        log.error(f"  Error Playwright en {url_sec}: {e}")
 
                browser.close()
 
        except Exception as e:
            log.error(f"  Error general Playwright TTA: {e}")
 
        log.info(f"    → {len(items)} documento(s) vía Playwright")
        return items
 
    # ── ORQUESTADOR ──────────────────────────────────────────────────────────
 
    def scrape_all(self) -> list[dict]:
        """
        Ejecuta todos los scrapers TTA y combina resultados sin duplicados.
        """
        all_items = []
 
        # 1. Página principal
        home_items = self.scrape_home()
        all_items.extend(home_items)
        time.sleep(2)
 
        # 2. Secciones de sentencias (HTML estático)
        tabla_items = self.scrape_sentencias_por_tribunal()
        all_items.extend(tabla_items)
        time.sleep(2)
 
        # 3. Playwright para contenido dinámico
        pw_items = self.scrape_con_playwright()
        all_items.extend(pw_items)
 
        # Deduplicar por doc_id
        seen = set()
        unique = []
        for item in all_items:
            if item["doc_id"] not in seen:
                seen.add(item["doc_id"])
                unique.append(item)
 
        log.info(f"  TTA total: {len(unique)} documento(s) nuevo(s)")
        return unique
