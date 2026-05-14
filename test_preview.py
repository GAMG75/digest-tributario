"""
Test de preview — genera el reporte HTML con datos de ejemplo reales
para validar formato, contenido y envío de email.
"""

import os, sys
from datetime import datetime

# ── Datos de ejemplo realistas (como los que extraería el scraper) ──────────

MOCK_DATA = {
    "circulares": [
        {
            "tipo": "Circular",
            "numero": "12",
            "fecha": "08-05-2025",
            "materia": "Instruye sobre modificaciones al procedimiento de devolución de IVA exportadores, Art. 36 D.L. 825",
            "url": "https://www.sii.cl/normativa_legislacion/circulares/2025/circ12_2025.pdf",
            "doc_id": "circ_12_08-05-2025",
        },
        {
            "tipo": "Circular",
            "numero": "11",
            "fecha": "25-04-2025",
            "materia": "Modifica Circular N° 57 de 2020, sobre declaración y pago de impuesto Global Complementario de contribuyentes con rentas del exterior",
            "url": "https://www.sii.cl/normativa_legislacion/circulares/2025/circ11_2025.pdf",
            "doc_id": "circ_11_25-04-2025",
        },
    ],
    "resoluciones": [
        {
            "tipo": "Resolución Exenta",
            "numero": "SII N° 35 Ex.",
            "fecha": "05-05-2025",
            "materia": "Establece obligación de timbraje electrónico de documentos tributarios para contribuyentes del régimen Pro-PYME",
            "url": "https://www.sii.cl/normativa_legislacion/resoluciones/2025/reso35ex_2025.pdf",
            "doc_id": "res_35_05-05-2025",
        },
    ],
    "jurisprudencia": [
        {
            "tipo": "Oficio/Jurisprudencia",
            "numero": "1847",
            "fecha": "30-04-2025",
            "materia": "Oficio N° 1847 — Tributación de indemnizaciones voluntarias pagadas a trabajadores en contexto de restructuración empresarial",
            "url": "https://www.sii.cl/normativa_legislacion/jurisprudencia_administrativa/2025/oficio1847_2025.pdf",
            "doc_id": "oficio_1847_30-04-2025",
        },
        {
            "tipo": "Oficio/Jurisprudencia",
            "numero": "1791",
            "fecha": "22-04-2025",
            "materia": "Oficio N° 1791 — Tratamiento tributario de criptomonedas para efectos del Impuesto a la Renta",
            "url": "https://www.sii.cl/normativa_legislacion/jurisprudencia_administrativa/2025/oficio1791_2025.pdf",
            "doc_id": "oficio_1791_22-04-2025",
        },
    ],
    "tta_sentencias": [
        {
            "tribunal": "TTA 1° Santiago",
            "region": "Metropolitana",
            "tipo": "Sentencia",
            "rol": "TT-1-00234-2024",
            "fecha": "07-05-2025",
            "materia": "Reclamación tributaria — Liquidación IVA por operaciones con proveedores cuestionados. Facturas falsas. Art. 23 N°5 D.L. 825",
            "resultado": "❌ Rechaza",
            "url": "https://www.tta.cl/sentencias/2025/TT-1-00234-2024.pdf",
            "doc_id": "tta_TT-1-00234-2024",
        },
        {
            "tribunal": "TTA 2° Santiago",
            "region": "Metropolitana",
            "tipo": "Sentencia",
            "rol": "TT-2-00189-2024",
            "fecha": "06-05-2025",
            "materia": "Impugnación de giro por diferencias en determinación de renta líquida imponible. Gastos rechazados Art. 31 LIR",
            "resultado": "✅ Acoge",
            "url": "https://www.tta.cl/sentencias/2025/TT-2-00189-2024.pdf",
            "doc_id": "tta_TT-2-00189-2024",
        },
        {
            "tribunal": "TTA Valparaíso",
            "region": "Valparaíso",
            "tipo": "Sentencia",
            "rol": "TT-3-00098-2024",
            "fecha": "05-05-2025",
            "materia": "Reclamación contra Resolución SII que deniega devolución de Pago Provisional por Utilidades Absorbidas (PPUA)",
            "resultado": "⚠️ Parcial",
            "url": "https://www.tta.cl/sentencias/2025/TT-3-00098-2024.pdf",
            "doc_id": "tta_TT-3-00098-2024",
        },
    ],
    "corte_suprema": [
        {
            "tribunal": "Corte Suprema",
            "tipo_tribunal": "Corte Suprema",
            "rol": "CS Rol 98.234-2024",
            "fecha": "02-05-2025",
            "materia": "Casación en el fondo — Impuesto Herencias. Valoración de acciones de sociedad cerrada para efectos del Art. 46 Ley N° 16.271",
            "resumen": "La Corte Suprema acoge recurso de casación interpuesto por el SII, estableciendo criterios para la valoración de participaciones en sociedades cerradas en el contexto del impuesto a las herencias.",
            "url": "https://buscador.pjud.cl/cs/98234-2024",
            "doc_id": "cs_98234-2024",
        },
    ],
}

print("Generando reporte de preview...")
print(f"Secciones: {list(MOCK_DATA.keys())}")
print(f"Total documentos: {sum(len(v) for v in MOCK_DATA.values())}")

# Generar el reporte usando el summarizer real (con Claude API si está disponible)
api_key = os.environ.get("ANTHROPIC_API_KEY", "")

if api_key and not api_key.startswith("sk-ant-DEMO"):
    print("\nUsando Claude API para generar resúmenes reales...")
    sys.path.insert(0, ".")
    from summarizer import TributaryReportSummarizer
    summarizer = TributaryReportSummarizer(api_key)
    html = summarizer.build_report(MOCK_DATA)
else:
    print("\nGenerando reporte con resúmenes de ejemplo (sin API key)...")
    # Reporte de ejemplo sin llamar a la API
    from summarizer import TributaryReportSummarizer, SECTION_META
    # Parchar temporalmente para no llamar a la API
    class MockSummarizer(TributaryReportSummarizer):
        def __init__(self): pass
        def _summarize_section(self, section_key, items):
            meta = SECTION_META.get(section_key, {})
            titulo = meta.get("titulo", section_key)
            docs_html = ""
            for item in items:
                materia = item.get("materia","") or item.get("resumen","")
                docs_html += f"""
                <h4>{item.get('tipo','Documento')} N° {item.get('numero', item.get('rol',''))}</h4>
                <p>{materia}</p>
                <ul>
                  <li><strong>Fecha:</strong> {item.get('fecha','')}</li>
                  <li><strong>Implicancia:</strong> Revisar cumplimiento y evaluar impacto en clientes afectados.</li>
                  <li><strong>Acción recomendada:</strong> Verificar aplicación en casos vigentes.</li>
                </ul>"""
            return f"<p><em>(Resumen generado por Claude AI en ejecución real)</em></p>{docs_html}"
    summarizer = MockSummarizer()
    html = summarizer.build_report(MOCK_DATA)

# Guardar preview
os.makedirs("logs", exist_ok=True)
with open("logs/preview.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n✅ Reporte generado: logs/preview.html ({len(html):,} bytes)")
print("Abrir ese archivo en un navegador para ver el email tal como llegará.")
