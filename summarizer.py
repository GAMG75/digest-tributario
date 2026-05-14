"""
TributaryReportSummarizer — Resume novedades tributarias usando Claude AI.
Especializado en lenguaje legal-tributario chileno.
"""

import logging
from datetime import datetime

import anthropic

log = logging.getLogger(__name__)

SECTION_META = {
    "circulares": {
        "emoji": "📋",
        "titulo": "Circulares SII",
        "descripcion": "Nuevas instrucciones del Servicio de Impuestos Internos",
        "color": "#1e40af",
    },
    "resoluciones": {
        "emoji": "📜",
        "titulo": "Resoluciones SII",
        "descripcion": "Nuevas resoluciones del Servicio de Impuestos Internos",
        "color": "#1e40af",
    },
    "jurisprudencia": {
        "emoji": "📂",
        "titulo": "Jurisprudencia Administrativa / Oficios SII",
        "descripcion": "Nuevos oficios y pronunciamientos del SII",
        "color": "#1e40af",
    },
    "tta_sentencias": {
        "emoji": "🏛️",
        "titulo": "Sentencias TTA — Tribunales Tributarios y Aduaneros",
        "descripcion": "Nuevas sentencias publicadas en www.tta.cl",
        "color": "#b45309",
    },
    "corte_suprema": {
        "emoji": "⚖️",
        "titulo": "Jurisprudencia Cortes — Materias Tributarias",
        "descripcion": "Sentencias de Cortes de Apelaciones y Corte Suprema en materia tributaria",
        "color": "#7c3aed",
    },
}

SYSTEM_PROMPT = """Eres un abogado tributarista experto en derecho tributario chileno con amplio conocimiento 
del Código Tributario, Ley sobre Impuesto a la Renta (LIR), Ley sobre Impuesto al Valor Agregado (LIVA), 
y la normativa del Servicio de Impuestos Internos (SII).

Tu tarea es analizar documentos tributarios (circulares, resoluciones, oficios, sentencias) y producir 
un resumen ejecutivo preciso y accionable para abogados y asesores tributarios.

Formato de respuesta ESTRICTAMENTE en HTML (sin tags html/head/body):
- Usa <h4> para subtítulos de cada documento
- Usa <p> para párrafos de análisis
- Usa <ul><li> para puntos clave o implicancias
- Usa <div class="alerta"> para advertencias importantes o cambios de criterio relevantes
- Usa <strong> para conceptos legales clave
- Mantén precisión técnica — este resumen lo leerán profesionales
- Idioma: español de Chile, terminología legal tributaria correcta
- Por cada documento indica: qué establece, a quiénes afecta, y qué acción se recomienda"""


class TributaryReportSummarizer:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def _summarize_section(self, section_key: str, items: list[dict]) -> str:
        """Llama a Claude para resumir una sección específica."""
        meta = SECTION_META.get(section_key, {"titulo": section_key})
        titulo = meta.get("titulo", section_key)

        # Construir el bloque de documentos
        docs_txt = []
        for i, item in enumerate(items[:20], 1):
            doc_lines = [f"DOCUMENTO {i}:"]
            for k, v in item.items():
                if k != "doc_id" and v:
                    doc_lines.append(f"  {k.upper()}: {str(v)[:300]}")
            docs_txt.append("\n".join(doc_lines))

        separador = "\n\n---\n\n"
        docs_joined = separador.join(docs_txt)
        prompt = f"""Analiza los siguientes {len(items)} documento(s) de la sección "{titulo}" y genera:

1. Un resumen ejecutivo de cada documento (qué establece, impacto, relevancia)
2. Las implicancias prácticas para contribuyentes y asesores
3. Si aplica: alertas sobre cambios de criterio, nuevas obligaciones o riesgos fiscales

DOCUMENTOS A ANALIZAR:
{docs_joined}"""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            log.error(f"Error resumiendo sección '{titulo}': {e}")
            return f"<p><em>Error al procesar esta sección. Revisar logs.</em></p>"

    def _build_document_table(self, items: list[dict], section_key: str) -> str:
        """Construye una tabla HTML con los documentos encontrados."""
        es_sii = section_key in ("circulares", "resoluciones", "jurisprudencia")

        if es_sii:
            headers = ["Tipo", "N°", "Fecha", "Materia", "Link"]
            rows = []
            for item in items[:20]:
                link = f'<a href="{item.get("url", "#")}" target="_blank">Ver →</a>'
                rows.append([
                    item.get("tipo", ""),
                    item.get("numero", ""),
                    item.get("fecha", ""),
                    item.get("materia", "")[:80] + ("..." if len(item.get("materia","")) > 80 else ""),
                    link,
                ])
        else:
            headers = ["Tribunal", "Rol", "Fecha", "Materia", "Link"]
            rows = []
            for item in items[:20]:
                link = f'<a href="{item.get("url", "#")}" target="_blank">Ver →</a>'
                rows.append([
                    item.get("tribunal", ""),
                    item.get("rol", ""),
                    item.get("fecha", ""),
                    item.get("materia", "")[:80] + ("..." if len(item.get("materia","")) > 80 else ""),
                    link,
                ])

        th_cells = "".join(f"<th>{h}</th>" for h in headers)
        tr_rows = ""
        for row in rows:
            td_cells = "".join(f"<td>{cell}</td>" for cell in row)
            tr_rows += f"<tr>{td_cells}</tr>"

        return f"""
        <table class="doc-table">
          <thead><tr>{th_cells}</tr></thead>
          <tbody>{tr_rows}</tbody>
        </table>"""

    def build_report(self, sections: dict[str, list[dict]]) -> str:
        """Genera el reporte HTML completo."""
        date_str = datetime.now().strftime("%A, %d de %B de %Y").capitalize()
        total = sum(len(v) for v in sections.values())

        # Agrupar secciones SII vs TTA vs PJUD
        sii_keys = [k for k in sections if k in ("circulares", "resoluciones", "jurisprudencia")]
        tta_keys = [k for k in sections if k == "tta_sentencias"]
        pjud_keys = [k for k in sections if k in ("corte_suprema", "pjud_buscador")]

        sections_html = []

        # Secciones SII
        if sii_keys:
            sections_html.append('<div class="fuente-header sii">🏛️ SERVICIO DE IMPUESTOS INTERNOS — www.sii.cl</div>')
            for key in sii_keys:
                if key not in sections:
                    continue
                items = sections[key]
                meta = SECTION_META.get(key, {})
                emoji = meta.get("emoji", "📄")
                titulo = meta.get("titulo", key)

                ai_summary = self._summarize_section(key, items)
                tabla = self._build_document_table(items, key)

                sections_html.append(f"""
                <div class="section">
                  <div class="section-header" style="border-color: {meta.get('color', '#1e40af')}">
                    <span class="section-emoji">{emoji}</span>
                    <div>
                      <h2 class="section-title">{titulo}</h2>
                      <span class="section-count">{len(items)} documento(s) nuevo(s)</span>
                    </div>
                  </div>
                  <div class="ai-summary">
                    <div class="ai-badge">🤖 Análisis IA</div>
                    {ai_summary}
                  </div>
                  <div class="table-wrap">
                    <h3 class="table-title">Documentos encontrados</h3>
                    {tabla}
                  </div>
                </div>""")

        # Secciones TTA
        if tta_keys:
            sections_html.append('<div class="fuente-header tta">🏛️ TRIBUNALES TRIBUTARIOS Y ADUANEROS — www.tta.cl</div>')
            for key in tta_keys:
                if key not in sections:
                    continue
                items = sections[key]
                meta = SECTION_META.get(key, {})
                emoji = meta.get("emoji", "🏛️")
                titulo = meta.get("titulo", key)

                ai_summary = self._summarize_section(key, items)
                tabla = self._build_document_table(items, key)

                sections_html.append(f"""
                <div class="section">
                  <div class="section-header" style="border-color: {meta.get('color', '#b45309')}">
                    <span class="section-emoji">{emoji}</span>
                    <div>
                      <h2 class="section-title">{titulo}</h2>
                      <span class="section-count">{len(items)} sentencia(s) nueva(s)</span>
                    </div>
                  </div>
                  <div class="ai-summary">
                    <div class="ai-badge">🤖 Análisis IA</div>
                    {ai_summary}
                  </div>
                  <div class="table-wrap">
                    <h3 class="table-title">Sentencias encontradas</h3>
                    {tabla}
                  </div>
                </div>""")

        # Secciones PJUD
        if pjud_keys:
            sections_html.append('<div class="fuente-header pjud">⚖️ PODER JUDICIAL — www.pjud.cl</div>')
            for key in pjud_keys:
                if key not in sections:
                    continue
                items = sections[key]
                meta = SECTION_META.get(key, {})
                emoji = meta.get("emoji", "⚖️")
                titulo = meta.get("titulo", key)

                ai_summary = self._summarize_section(key, items)
                tabla = self._build_document_table(items, key)

                sections_html.append(f"""
                <div class="section">
                  <div class="section-header" style="border-color: {meta.get('color', '#7c3aed')}">
                    <span class="section-emoji">{emoji}</span>
                    <div>
                      <h2 class="section-title">{titulo}</h2>
                      <span class="section-count">{len(items)} sentencia(s) nueva(s)</span>
                    </div>
                  </div>
                  <div class="ai-summary">
                    <div class="ai-badge">🤖 Análisis IA</div>
                    {ai_summary}
                  </div>
                  <div class="table-wrap">
                    <h3 class="table-title">Sentencias encontradas</h3>
                    {tabla}
                  </div>
                </div>""")

        body_content = "\n".join(sections_html)

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f1f5f9;
          padding: 20px; color: #1e293b; font-size: 14px; }}
  .container {{ max-width: 800px; margin: 0 auto; }}

  /* Header */
  .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
             border-radius: 12px 12px 0 0; padding: 28px 36px; text-align: center; }}
  .header-logo {{ font-size: 28px; margin-bottom: 6px; }}
  .header h1 {{ color: #fff; font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
  .header-date {{ color: #94a3b8; font-size: 13px; }}
  .header-badge {{ display: inline-block; background: #3b82f6; color: #fff;
                   border-radius: 20px; padding: 4px 14px; font-size: 12px;
                   margin-top: 10px; font-weight: 600; }}

  /* Body */
  .body {{ background: #fff; padding: 32px 36px; }}

  /* Fuente headers */
  .fuente-header {{ font-size: 11px; font-weight: 700; letter-spacing: 1.5px;
                    text-transform: uppercase; padding: 10px 16px;
                    border-radius: 6px; margin: 24px 0 16px; }}
  .fuente-header.sii {{ background: #dbeafe; color: #1d4ed8; }}
  .fuente-header.tta {{ background: #fef3c7; color: #92400e; }}
  .fuente-header.pjud {{ background: #ede9fe; color: #6d28d9; }}

  /* Sections */
  .section {{ margin-bottom: 32px; border: 1px solid #e2e8f0;
              border-radius: 10px; overflow: hidden; }}
  .section-header {{ display: flex; align-items: center; gap: 14px;
                     padding: 16px 20px; border-left: 5px solid;
                     background: #f8fafc; }}
  .section-emoji {{ font-size: 24px; }}
  .section-title {{ font-size: 16px; font-weight: 700; color: #1e293b; margin-bottom: 2px; }}
  .section-count {{ font-size: 12px; color: #64748b; font-weight: 500; }}

  /* AI Summary */
  .ai-summary {{ padding: 20px 24px; border-bottom: 1px solid #e2e8f0; }}
  .ai-badge {{ display: inline-block; background: #f0fdf4; color: #15803d;
               border: 1px solid #bbf7d0; border-radius: 4px;
               padding: 2px 10px; font-size: 11px; font-weight: 600;
               margin-bottom: 12px; }}
  .ai-summary h4 {{ color: #1e293b; margin: 14px 0 6px; font-size: 14px; }}
  .ai-summary p {{ color: #374151; line-height: 1.6; margin-bottom: 8px; }}
  .ai-summary ul {{ padding-left: 18px; }}
  .ai-summary li {{ color: #4b5563; line-height: 1.7; margin-bottom: 4px; }}
  .ai-summary strong {{ color: #111827; }}
  .ai-summary a {{ color: #2563eb; text-decoration: none; }}
  .ai-summary .alerta {{ background: #fef3c7; border-left: 4px solid #f59e0b;
                          padding: 10px 14px; border-radius: 0 6px 6px 0;
                          margin: 12px 0; font-size: 13px; color: #92400e; }}

  /* Table */
  .table-wrap {{ padding: 16px 20px 20px; }}
  .table-title {{ font-size: 13px; color: #64748b; font-weight: 600;
                  margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .doc-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .doc-table th {{ background: #f1f5f9; color: #475569; font-weight: 600;
                   padding: 8px 10px; text-align: left; border-bottom: 2px solid #e2e8f0; }}
  .doc-table td {{ padding: 8px 10px; border-bottom: 1px solid #f1f5f9;
                   color: #374151; vertical-align: top; }}
  .doc-table tr:last-child td {{ border-bottom: none; }}
  .doc-table a {{ color: #2563eb; font-weight: 600; white-space: nowrap; }}

  /* Footer */
  .footer {{ background: #f8fafc; border-top: 1px solid #e2e8f0;
             padding: 16px 36px; text-align: center;
             border-radius: 0 0 12px 12px; }}
  .footer p {{ color: #94a3b8; font-size: 11px; line-height: 1.6; }}
  .footer a {{ color: #2563eb; }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="header-logo">📊</div>
      <h1>Novedades Tributarias Chile</h1>
      <div class="header-date">{date_str}</div>
      <div class="header-badge">{total} novedad(es) detectada(s)</div>
    </div>
    <div class="body">
      {body_content}
    </div>
    <div class="footer">
      <p>
        Generado automáticamente por el sistema de monitoreo tributario.<br>
        Fuentes: <a href="https://www.sii.cl">www.sii.cl</a> · 
        <a href="https://www.tta.cl">www.tta.cl</a> · 
        <a href="https://www.pjud.cl">www.pjud.cl</a><br>
        <strong>Este reporte es informativo.</strong> Verifique siempre en las fuentes oficiales.
        Generado el {datetime.now():%d/%m/%Y a las %H:%M} hrs.
      </p>
    </div>
  </div>
</body>
</html>"""
