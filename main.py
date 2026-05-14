"""
Digest Tributario Chile — Orquestador principal
Monitorea SII y PJUD extrayendo novedades normativas y jurisprudencia tributaria.

Ejecución:
  python main.py                  # Ejecución normal
  python main.py --force          # Ignora estado anterior (reenvía todo)
  python main.py --dry-run        # Ejecuta sin enviar email

Cron (VPS):
  0 1 * * * cd /ruta/proyecto && /usr/bin/python3 main.py >> logs/digest.log 2>&1
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from config import load_config
from scrapers.sii_scraper import SIIScraper
from scrapers.pjud_scraper import PJUDScraper
from scrapers.tta_scraper import TTAScraper
from state_manager import StateManager
from summarizer import TributaryReportSummarizer
from mailer import send_report

# ── Logging ─────────────────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"logs/digest-{datetime.now():%Y-%m-%d}.log"),
    ],
)
log = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser(description="Digest Tributario Chile")
    p.add_argument("--force", action="store_true", help="Ignorar estado previo")
    p.add_argument("--dry-run", action="store_true", help="No enviar email")
    p.add_argument("--only", choices=["sii", "pjud", "tta"], help="Ejecutar solo una fuente")
    return p.parse_args()


def main():
    args = parse_args()
    config = load_config()
    state = StateManager("state.json")

    log.info("=" * 70)
    log.info(f"🇨🇱  DIGEST TRIBUTARIO CHILE — {datetime.now():%Y-%m-%d %H:%M}")
    log.info("=" * 70)

    all_sections: dict[str, list[dict]] = {}

    # ── SII ──────────────────────────────────────────────────────────────────
    if not args.only or args.only == "sii":
        log.info("\n📋 [SII] Iniciando scraping...")
        sii = SIIScraper(state, force=args.force)
        sii_data = sii.scrape_all()

        if sii_data:
            for key, items in sii_data.items():
                if items:
                    all_sections[key] = items
                    log.info(f"  ✅ SII {key}: {len(items)} novedad(es)")
                else:
                    log.info(f"  — SII {key}: sin novedades")
        else:
            log.info("  — SII: sin novedades hoy")

    # ── TTA ──────────────────────────────────────────────────────────────────
    if not args.only or args.only == "tta":
        log.info("\n🏛️  [TTA] Iniciando scraping www.tta.cl...")
        tta = TTAScraper(state, force=args.force)
        tta_items = tta.scrape_all()

        if tta_items:
            all_sections["tta_sentencias"] = tta_items
            log.info(f"  ✅ TTA: {len(tta_items)} novedad(es)")
        else:
            log.info("  — TTA: sin novedades hoy")

    # ── PJUD ─────────────────────────────────────────────────────────────────
    if not args.only or args.only == "pjud":
        log.info("\n⚖️  [PJUD] Iniciando scraping...")
        pjud = PJUDScraper(state, force=args.force)
        pjud_data = pjud.scrape_all()

        if pjud_data:
            for key, items in pjud_data.items():
                if items:
                    all_sections[key] = items
                    log.info(f"  ✅ PJUD {key}: {len(items)} novedad(es)")
                else:
                    log.info(f"  — PJUD {key}: sin novedades")
        else:
            log.info("  — PJUD: sin novedades hoy")

    # ── Verificar si hay novedades ────────────────────────────────────────────
    total_items = sum(len(v) for v in all_sections.values())
    if total_items == 0:
        log.info("\n✅ Sin novedades hoy. No se envía email.")
        state.save()
        return

    log.info(f"\n📊 Total novedades: {total_items} items en {len(all_sections)} sección(es)")

    # ── Generar reporte con Claude ────────────────────────────────────────────
    log.info("\n🤖 Generando resumen con Claude AI...")
    summarizer = TributaryReportSummarizer(config["anthropic_api_key"])
    html_report = summarizer.build_report(all_sections)
    log.info("  ✅ Reporte generado")

    # ── Enviar email ──────────────────────────────────────────────────────────
    if args.dry_run:
        log.info("\n🔍 DRY RUN — email no enviado. Guardando reporte en logs/preview.html")
        with open("logs/preview.html", "w", encoding="utf-8") as f:
            f.write(html_report)
    else:
        log.info(f"\n📧 Enviando a {len(config['recipients'])} destinatario(s)...")
        send_report(
            html_content=html_report,
            recipients=config["recipients"],
            subject=f"📋 Novedades Tributarias Chile — {datetime.now():%d/%m/%Y}",
            config=config,
        )
        log.info("  ✅ Email enviado")

    # ── Guardar estado ────────────────────────────────────────────────────────
    state.save()
    log.info("\n✅ Estado actualizado. Proceso completado.")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
