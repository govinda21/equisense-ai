"""
PDF report generation for EquiSense AI.
Mirrors the UI layout exactly, using correct data paths from report_sample.json.

Data path reference (all paths from root of report_data dict):
  decision.*                          - action, rating, score, letter_grade, confidence_score,
                                        stars, executive_summary, short_term_outlook,
                                        long_term_outlook, growth_drivers, competitive_advantages,
                                        key_risks, top_reasons_for, top_reasons_against,
                                        price_target_12m, professional_rationale
  fundamentals.details.*             - dcf_valuation, basic_fundamentals, pillar_scores,
                                        trading_recommendations, risk_assessment,
                                        deep_financial_analysis, governance_analysis
  analyst_recommendations.details.*  - target_prices, consensus_analysis,
                                        recommendation_summary
  news_sentiment.details.*           - score, professional_sentiment, valuepickr_analysis
  peer_analysis.details.*            - relative_position, valuation_summary, peers_identified
"""

from __future__ import annotations

import io
import base64
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor, white, Color
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, ListFlowable, ListItem, KeepTogether,
    )
    from reportlab.platypus.flowables import HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("ReportLab not available. Run: pip install reportlab")

logger = logging.getLogger(__name__)

# Usable page width (A4 minus 2x 0.75" margins)
PAGE_W = A4[0] - 2 * 0.75 * inch

# ── Colour palette ────────────────────────────────────────────────────────────
_BLUE        = HexColor("#1e40af")
_BLUE_LIGHT  = HexColor("#3b82f6")
_BLUE_BG     = HexColor("#eff6ff")
_GREEN       = HexColor("#16a34a")
_GREEN_BG    = HexColor("#f0fdf4")
_RED         = HexColor("#dc2626")
_RED_BG      = HexColor("#fef2f2")
_PURPLE      = HexColor("#7c3aed")
_PURPLE_BG   = HexColor("#f5f3ff")
_AMBER       = HexColor("#d97706")
_AMBER_BG    = HexColor("#fffbeb")
_GRAY_DARK   = HexColor("#1e293b")
_GRAY_MID    = HexColor("#64748b")
_GRAY_LIGHT  = HexColor("#f8fafc")
_BORDER      = HexColor("#e2e8f0")
_WHITE       = white


# ── Safe data helpers ─────────────────────────────────────────────────────────

def _get(d: dict, *path, default=None):
    """Safe nested dict accessor."""
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _scalar(value: Any) -> Optional[float]:
    """Extract float from a plain scalar or a dict-wrapped metric."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for k in ("score", "value", "latest", "current", "price", "mean", "amount"):
            c = value.get(k)
            if isinstance(c, (int, float)):
                return float(c)
        for c in value.values():
            if isinstance(c, (int, float)):
                return float(c)
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any, prefix: str = "", suffix: str = "", decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    v = _scalar(value)
    if v is not None:
        return f"{prefix}{v:,.{decimals}f}{suffix}"
    return str(value)


def _pct(value: Any, decimals: int = 1, always_sign: bool = True) -> str:
    """Format a 0-1 ratio as percentage. Values > 1.5 treated as already-pct."""
    v = _scalar(value)
    if v is None:
        return "N/A"
    pv = v * 100 if abs(v) <= 1.5 else v
    sign = "+" if always_sign and pv >= 0 else ""
    return f"{sign}{pv:.{decimals}f}%"


def _inr(value: Any, decimals: int = 2) -> str:
    v = _scalar(value)
    if v is None:
        return "N/A"
    return f"\u20b9{v:,.{decimals}f}"


def _cr(value: Any) -> str:
    """Large INR value formatted as Crores."""
    v = _scalar(value)
    if v is None:
        return "N/A"
    return f"\u20b9{v / 1e7:,.1f} Cr"


def _is_inr(d: dict) -> bool:
    return str(d.get("ticker", "")).upper().endswith((".NS", ".BO"))


def _cur(d: dict) -> str:
    return "\u20b9" if _is_inr(d) else "$"


# ── Colour helpers ────────────────────────────────────────────────────────────

def _action_color(action: str) -> Color:
    a = str(action).upper()
    if "BUY" in a:
        return _GREEN
    if "SELL" in a:
        return _RED
    return _AMBER


def _grade_color(grade: str) -> Color:
    g = str(grade).upper()
    if g.startswith("A"):
        return _GREEN
    if g.startswith("B"):
        return _BLUE_LIGHT
    if g.startswith("C"):
        return _AMBER
    return _RED


def _score_color_hex(score) -> str:
    v = _scalar(score)
    if v is None:
        return "64748b"
    if v >= 70:
        return "16a34a"
    if v >= 50:
        return "d97706"
    return "dc2626"


# ── Layout helpers ────────────────────────────────────────────────────────────

def _kv_table(rows: List[tuple], col_widths=None) -> Table:
    col_widths = col_widths or [2.6 * inch, 3.4 * inch]
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME",      (0, 0), (0, -1),  "Helvetica-Bold"),
        ("FONTNAME",      (1, 0), (1, -1),  "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, _BORDER),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [_GRAY_LIGHT, _WHITE]),
    ]))
    return t


def _section_hdr(title: str, s) -> List:
    return [
        Spacer(1, 10),
        Paragraph(title, s["SectionHeader"]),
        HRFlowable(width="100%", thickness=0.75, color=_BLUE),
        Spacer(1, 6),
    ]


def _bullets(items: List[str], style) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(str(i), style), leftIndent=10) for i in items if i],
        bulletType="bullet",
        start="\u2022",
        leftIndent=16,
        spaceBefore=2,
        spaceAfter=2,
    )


# ── Main generator class ──────────────────────────────────────────────────────

class PDFReportGenerator:

    def __init__(self):
        self.styles = None
        if PDF_AVAILABLE:
            self._init_styles()

    def _init_styles(self):
        ss = getSampleStyleSheet()

        def add(name, parent, **kw):
            if name not in ss:
                ss.add(ParagraphStyle(name=name, parent=ss[parent], **kw))

        add("Title1",         "Title",   fontSize=20, spaceAfter=4, alignment=TA_CENTER,
            textColor=_BLUE, fontName="Helvetica-Bold")
        add("Subtitle",       "Normal",  fontSize=10, spaceAfter=3, alignment=TA_CENTER,
            textColor=_GRAY_MID)
        add("SectionHeader",  "Normal",  fontSize=13, spaceAfter=4, spaceBefore=8,
            textColor=_BLUE, fontName="Helvetica-Bold")
        add("SubHeader",      "Normal",  fontSize=10, spaceAfter=3, spaceBefore=5,
            textColor=_GRAY_DARK, fontName="Helvetica-Bold")
        add("Body",           "Normal",  fontSize=9,  spaceAfter=3, alignment=TA_JUSTIFY,
            textColor=_GRAY_DARK, leading=13)
        add("BodyLeft",       "Normal",  fontSize=9,  spaceAfter=2,
            textColor=_GRAY_DARK, leading=12)
        add("Small",          "Normal",  fontSize=8,  textColor=_GRAY_MID, leading=11)
        add("Disclaimer",     "Normal",  fontSize=7,  spaceAfter=2, alignment=TA_CENTER,
            textColor=_GRAY_MID, fontName="Helvetica-Oblique")
        add("CardLabel",      "Normal",  fontSize=7,  textColor=_GRAY_MID,
            fontName="Helvetica-Bold", alignment=TA_CENTER)
        add("CardSub",        "Normal",  fontSize=8,  textColor=_GRAY_MID,
            alignment=TA_CENTER)

        self.styles = ss

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_report(self, d: Dict[str, Any]) -> io.BytesIO:
        if not PDF_AVAILABLE:
            raise RuntimeError("ReportLab is not installed: pip install reportlab")

        ticker = d.get("ticker", "")
        buf    = io.BytesIO()
        doc    = SimpleDocTemplate(
            buf, pagesize=A4,
            rightMargin=0.75 * inch, leftMargin=0.75 * inch,
            topMargin=0.65 * inch,   bottomMargin=0.5 * inch,
            title=f"EquiSense Research - {ticker}",
            author="EquiSense AI",
        )

        story: List = []
        story.extend(self._cover(d))
        story.append(PageBreak())
        story.extend(self._recommendation_section(d))
        story.extend(self._dcf_scenarios(d))
        story.extend(self._outlook_section(d))
        story.extend(self._comprehensive_fundamentals(d))
        story.extend(self._deep_financial_analysis(d))
        story.extend(self._earnings_quality(d))
        story.extend(self._peer_analysis(d))
        story.extend(self._governance(d))
        story.extend(self._analyst_section(d))
        story.extend(self._sector_macro(d))
        story.extend(self._appendix(d))

        doc.build(story)
        buf.seek(0)
        logger.info(f"PDF built for {ticker} ({buf.getbuffer().nbytes:,} bytes)")
        return buf

    # ── COVER PAGE ────────────────────────────────────────────────────────────

    def _cover(self, d: Dict) -> List:
        s       = self.styles
        ticker  = d.get("ticker", "N/A")
        dec     = d.get("decision", {}) or {}
        fi_det  = _get(d, "fundamentals", "details") or {}
        bf      = fi_det.get("basic_fundamentals", {}) or {}

        company   = bf.get("companyName") or bf.get("company_name") or ticker
        sector    = bf.get("sector", "")
        industry  = bf.get("industry", "")
        exchange  = _get(fi_det, "indian_market_data", "exchange") or ""
        cur_sym   = _cur(d)

        action    = str(dec.get("action", "")).upper()
        rating    = dec.get("rating") or dec.get("score")
        grade     = dec.get("letter_grade", "")
        confidence= dec.get("confidence_score")
        stars     = dec.get("stars", "")
        price     = bf.get("current_price") or d.get("currentPrice")
        exec_sum  = dec.get("executive_summary") or d.get("executive_summary", "")

        elems = [
            Spacer(1, 0.35 * inch),
            Paragraph("EquiSense AI  |  Equity Research Report", s["Subtitle"]),
            Spacer(1, 6),
            Paragraph(company, s["Title1"]),
            Paragraph(f"{ticker}  |  {sector}  |  {exchange}", s["Subtitle"]),
            Spacer(1, 10),
            HRFlowable(width="100%", thickness=2, color=_BLUE),
            Spacer(1, 12),
        ]

        # 4-column banner
        conf_str  = f"{int(float(confidence))}%" if confidence else "N/A"
        rate_str  = f"{_fmt(rating, decimals=1)}/5.0" if rating else ""
        banner = Table(
            [
                ["CURRENT PRICE", "RECOMMENDATION", "GRADE", "CONFIDENCE"],
                [
                    f"{cur_sym}{_fmt(price)}" if price else "N/A",
                    f"{action}  {stars}" if stars else action,
                    grade,
                    conf_str,
                ],
                ["Live market price", rate_str, "", "Conviction level"],
            ],
            colWidths=[PAGE_W / 4] * 4,
        )
        banner.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica"),
            ("FONTSIZE",      (0, 0), (-1, 0),  7),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  _GRAY_MID),
            ("FONTNAME",      (0, 1), (-1, 1),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 1), (-1, 1),  15),
            ("TEXTCOLOR",     (0, 1), (0, 1),   _GRAY_DARK),
            ("TEXTCOLOR",     (1, 1), (1, 1),   _action_color(action)),
            ("TEXTCOLOR",     (2, 1), (2, 1),   _grade_color(grade)),
            ("TEXTCOLOR",     (3, 1), (3, 1),   _BLUE),
            ("FONTNAME",      (0, 2), (-1, 2),  "Helvetica"),
            ("FONTSIZE",      (0, 2), (-1, 2),  7),
            ("TEXTCOLOR",     (0, 2), (-1, 2),  _GRAY_MID),
            ("BACKGROUND",    (0, 0), (-1, -1), _GRAY_LIGHT),
            ("BOX",           (0, 0), (-1, -1), 0.5, _BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, _BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elems.append(banner)
        elems.append(Spacer(1, 14))

        if exec_sum:
            elems.append(Paragraph("Executive Summary", s["SubHeader"]))
            elems.append(Paragraph(str(exec_sum), s["Body"]))
            elems.append(Spacer(1, 10))

        meta = [
            ("Report Date",  datetime.now().strftime("%B %d, %Y")),
            ("Analyst",      "EquiSense AI"),
            ("Ticker",       ticker),
            ("Sector",       f"{sector} / {industry}" if industry else sector),
            ("Exchange",     exchange or ("NSE/BSE" if _is_inr(d) else "NYSE/NASDAQ")),
        ]
        elems.append(_kv_table(meta, col_widths=[1.8 * inch, 4.2 * inch]))
        elems.append(Spacer(1, 12))
        elems.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
        elems.append(Spacer(1, 4))
        elems.append(Paragraph(
            "This report is for informational purposes only and does not constitute investment advice.",
            s["Disclaimer"],
        ))
        return elems

    # ── INVESTMENT RECOMMENDATION ─────────────────────────────────────────────

    def _recommendation_section(self, d: Dict) -> List:
        s      = self.styles
        dec    = d.get("decision", {}) or {}
        fi_det = _get(d, "fundamentals", "details") or {}
        bf     = fi_det.get("basic_fundamentals", {}) or {}
        dcf    = fi_det.get("dcf_valuation", {}) or {}
        ar_det = _get(d, "analyst_recommendations", "details") or {}
        cur_sym = _cur(d)

        price   = bf.get("current_price") or d.get("currentPrice")
        pt_mean = _get(ar_det, "target_prices", "mean")
        impl_ret= _get(ar_det, "consensus_analysis", "implied_return")

        # DCF base case from scenario_results[scenario="Base"].result.intrinsic_value_per_share
        base_iv = None
        for scen in dcf.get("scenario_results", []):
            if str(scen.get("scenario", "")).lower() == "base":
                base_iv = _get(scen, "result", "intrinsic_value_per_share")
                break
        if base_iv is None:
            base_iv = dcf.get("intrinsic_value")

        elems = _section_hdr("Investment Recommendation", s)

        # 4 metric cards
        ret_sign = "+" if (impl_ret or 0) >= 0 else ""
        ret_str  = f"{ret_sign}{_fmt(impl_ret, decimals=1)}%" if impl_ret is not None else "N/A"

        card_data = [
            ["CURRENT PRICE", "PRICE TARGET", "EXPECTED RETURN", "DCF VALUATION"],
            [
                f"{cur_sym}{_fmt(price)}"            if price    else "N/A",
                f"{cur_sym}{_fmt(pt_mean, decimals=0)}" if pt_mean else "N/A",
                ret_str,
                f"{cur_sym}{_fmt(base_iv)}"          if base_iv  else "N/A",
            ],
            ["Live market price", "Analyst consensus target", "12-month forecast", "Base case scenario"],
        ]
        cards = Table(card_data, colWidths=[PAGE_W / 4] * 4)
        cards.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0),  7),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  _GRAY_MID),
            ("FONTNAME",      (0, 1), (-1, 1),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 1), (-1, 1),  14),
            ("TEXTCOLOR",     (0, 1), (0, 1),   _GRAY_DARK),
            ("TEXTCOLOR",     (1, 1), (1, 1),   _GREEN),
            ("TEXTCOLOR",     (2, 1), (2, 1),   _BLUE),
            ("TEXTCOLOR",     (3, 1), (3, 1),   _PURPLE),
            ("FONTNAME",      (0, 2), (-1, 2),  "Helvetica"),
            ("FONTSIZE",      (0, 2), (-1, 2),  8),
            ("TEXTCOLOR",     (0, 2), (-1, 2),  _GRAY_MID),
            ("BACKGROUND",    (0, 0), (0, -1),  _WHITE),
            ("BACKGROUND",    (1, 0), (1, -1),  _GREEN_BG),
            ("BACKGROUND",    (2, 0), (2, -1),  _BLUE_BG),
            ("BACKGROUND",    (3, 0), (3, -1),  _PURPLE_BG),
            ("BOX",           (0, 0), (0, -1),  1,   _BORDER),
            ("BOX",           (1, 0), (1, -1),  1.5, _GREEN),
            ("BOX",           (2, 0), (2, -1),  1.5, _BLUE_LIGHT),
            ("BOX",           (3, 0), (3, -1),  1.5, _PURPLE),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        elems.append(cards)
        elems.append(Spacer(1, 10))

        # Valuation warnings
        warnings = _get(fi_det, "dcf_valuation", "sanity_check", "warnings") or []
        if warnings:
            warn_rows = [["  Valuation Model Warnings"]] + [[f"  * {w}"] for w in warnings]
            wt = Table(warn_rows, colWidths=[PAGE_W])
            wt.setStyle(TableStyle([
                ("FONTNAME",      (0, 0), (0, 0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0, 0), (-1, -1), 9),
                ("TEXTCOLOR",     (0, 0), (0, 0),   _AMBER),
                ("TEXTCOLOR",     (0, 1), (-1, -1), HexColor("#92400e")),
                ("BACKGROUND",    (0, 0), (-1, -1), _AMBER_BG),
                ("BOX",           (0, 0), (-1, -1), 1, HexColor("#fcd34d")),
                ("TOPPADDING",    (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
            ]))
            elems.append(wt)
            elems.append(Spacer(1, 8))

        # Professional rationale
        rationale = dec.get("professional_rationale", "")
        if rationale:
            elems.append(Paragraph(str(rationale), s["Body"]))
            elems.append(Spacer(1, 6))

        # Bull / Bear reasons
        reasons_for     = dec.get("top_reasons_for") or []
        reasons_against = dec.get("top_reasons_against") or dec.get("key_risks") or []
        if reasons_for or reasons_against:
            bull_text = "\n".join(f"   * {r}" for r in reasons_for)    or "   —"
            bear_text = "\n".join(f"   * {r}" for r in reasons_against) or "   —"
            t = Table(
                [[Paragraph(f"Bull Case\n{bull_text}", s["BodyLeft"]),
                  Paragraph(f"Bear Case\n{bear_text}", s["BodyLeft"])]],
                colWidths=[PAGE_W / 2, PAGE_W / 2],
            )
            t.setStyle(TableStyle([
                ("VALIGN",       (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING",  (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING",   (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
                ("BOX",          (0, 0), (0, -1),  0.5, _GREEN),
                ("BOX",          (1, 0), (1, -1),  0.5, _RED),
                ("BACKGROUND",   (0, 0), (0, -1),  _GREEN_BG),
                ("BACKGROUND",   (1, 0), (1, -1),  _RED_BG),
            ]))
            elems.append(t)
            elems.append(Spacer(1, 6))

        return elems

    # ── DCF SCENARIOS ─────────────────────────────────────────────────────────

    def _dcf_scenarios(self, d: Dict) -> List:
        s        = self.styles
        dcf      = _get(d, "fundamentals", "details", "dcf_valuation") or {}
        scenarios= dcf.get("scenario_results", [])
        cur_sym  = _cur(d)

        if not scenarios:
            return []

        elems = _section_hdr("DCF Scenario Analysis", s)

        col_map = {
            "bull": (_GREEN,      _GREEN_BG),
            "base": (_BLUE,       _BLUE_BG),
            "bear": (_RED,        _RED_BG),
        }

        for scen in scenarios:
            name = str(scen.get("scenario", "")).lower()
            prob = scen.get("probability", 0)
            iv   = _get(scen, "result", "intrinsic_value_per_share")
            fg, bg = col_map.get(name, (_GRAY_MID, _GRAY_LIGHT))
            label = name.title()
            iv_str = f"{cur_sym}{_fmt(iv)}" if iv is not None else "N/A"

            row_data = [[
                Paragraph(f"  {label}", s["BodyLeft"]),
                Paragraph(f"{int(prob * 100)}% probability", s["BodyLeft"]),
                Paragraph(iv_str, s["BodyLeft"]),
            ]]
            rt = Table(row_data, colWidths=[0.9*inch, PAGE_W - 2.4*inch, 1.5*inch])
            rt.setStyle(TableStyle([
                ("TEXTCOLOR",     (0, 0), (0, 0),  _WHITE),
                ("BACKGROUND",    (0, 0), (0, 0),  fg),
                ("BACKGROUND",    (1, 0), (-1, 0), bg),
                ("FONTNAME",      (0, 0), (-1, -1),"Helvetica-Bold"),
                ("FONTSIZE",      (0, 0), (-1, -1), 9),
                ("ALIGN",         (2, 0), (2, 0),  "RIGHT"),
                ("TEXTCOLOR",     (2, 0), (2, 0),  fg),
                ("FONTSIZE",      (2, 0), (2, 0),  11),
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("BOX",           (0, 0), (-1, -1), 0.5, fg),
                ("TOPPADDING",    (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ]))
            elems.append(rt)
            elems.append(Spacer(1, 4))

        # Key assumptions + stop loss
        ka   = dcf.get("key_assumptions", {}) or {}
        rows = []
        wacc = ka.get("wacc")
        tg   = ka.get("terminal_growth")
        stop = dcf.get("stop_loss")
        buy  = dcf.get("buy_zone")
        iv_main = dcf.get("intrinsic_value")
        mos  = dcf.get("margin_of_safety")
        cur  = _cur(d)
        if wacc    is not None: rows.append(("WACC",                f"{wacc * 100:.2f}%"))
        if tg      is not None: rows.append(("Terminal Growth",      f"{tg * 100:.2f}%"))
        if iv_main is not None: rows.append(("Intrinsic Value (DCF)",f"{cur}{_fmt(iv_main)}"))
        if mos     is not None: rows.append(("Margin of Safety",     _pct(mos)))
        if stop    is not None: rows.append(("Stop Loss",            f"{cur}{_fmt(stop)}"))
        if buy     is not None: rows.append(("Buy Zone",             f"{cur}{_fmt(buy)}"))
        if rows:
            elems.append(Spacer(1, 4))
            elems.append(_kv_table(rows))

        elems.append(Spacer(1, 6))
        return elems

    # ── GROWTH DRIVERS + OUTLOOK ──────────────────────────────────────────────

    def _outlook_section(self, d: Dict) -> List:
        s   = self.styles
        dec = d.get("decision", {}) or {}

        growth_drivers = dec.get("growth_drivers") or []
        comp_adv       = dec.get("competitive_advantages") or []
        key_risks      = dec.get("key_risks") or []
        short_outlook  = dec.get("short_term_outlook", "")
        long_outlook   = dec.get("long_term_outlook", "")

        elems = []

        if any([growth_drivers, comp_adv, key_risks]):
            elems.extend(_section_hdr("Strategic Overview", s))

            def card_lines(title, items):
                out = [Paragraph(f"{title}", s["SubHeader"])]
                for item in items:
                    out.append(Paragraph(f"* {item}", s["Small"]))
                return out

            row = [[
                card_lines("Growth Drivers",        growth_drivers),
                card_lines("Competitive Advantages", comp_adv),
                card_lines("Key Risks",              key_risks),
            ]]
            ct = Table(row, colWidths=[PAGE_W / 3] * 3)
            ct.setStyle(TableStyle([
                ("VALIGN",       (0, 0), (-1, -1), "TOP"),
                ("BOX",          (0, 0), (0, -1),  0.5, _BORDER),
                ("BOX",          (1, 0), (1, -1),  0.5, _BORDER),
                ("BOX",          (2, 0), (2, -1),  0.5, _BORDER),
                ("LEFTPADDING",  (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING",   (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
            ]))
            elems.append(ct)
            elems.append(Spacer(1, 8))

        if short_outlook or long_outlook:
            elems.extend(_section_hdr("Investment Outlook", s))
            if short_outlook:
                elems.append(Paragraph("Short-Term Outlook (3-6 Months)", s["SubHeader"]))
                elems.append(Paragraph(str(short_outlook), s["Body"]))
                elems.append(Spacer(1, 6))
            if long_outlook:
                elems.append(Paragraph("Long-Term Outlook (12-36 Months)", s["SubHeader"]))
                elems.append(Paragraph(str(long_outlook), s["Body"]))
                elems.append(Spacer(1, 6))

        return elems

    # ── COMPREHENSIVE FUNDAMENTAL ANALYSIS ────────────────────────────────────

    def _comprehensive_fundamentals(self, d: Dict) -> List:
        s      = self.styles
        fi_det = _get(d, "fundamentals", "details") or {}
        ps     = fi_det.get("pillar_scores", {}) or {}
        tr     = fi_det.get("trading_recommendations", {}) or {}
        risk   = fi_det.get("risk_assessment", {}) or {}
        cur    = _cur(d)

        fh  = _get(ps, "financial_health",  "score")
        val = _get(ps, "valuation",          "score")
        grw = _get(ps, "growth_prospects",   "score")
        gov = _get(ps, "governance",         "score")
        mac = _get(ps, "macro_sensitivity",  "score")

        elems = _section_hdr("Comprehensive Fundamental Analysis", s)

        # 5-score grid
        scores = [
            ("FINANCIAL HEALTH", fh),
            ("VALUATION",        val),
            ("GROWTH",           grw),
            ("GOVERNANCE",       gov),
            ("MACRO",            mac),
        ]
        label_row = [[Paragraph(lbl, s["CardLabel"]) for lbl, _ in scores]]
        value_row = [[
            Paragraph(
                f'<font color="#{_score_color_hex(sc)}"><b>{int(sc) if sc is not None else "-"}</b></font>',
                ParagraphStyle("_cv", parent=s["Normal"], fontSize=18, fontName="Helvetica-Bold",
                               alignment=TA_CENTER)
            ) for _, sc in scores
        ]]
        sub_row   = [[Paragraph("Score", s["CardSub"]) for _ in scores]]

        st = Table(label_row + value_row + sub_row, colWidths=[PAGE_W / 5] * 5)
        st.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND",    (0, 0), (-1, -1), _GRAY_LIGHT),
            ("BOX",           (0, 0), (-1, -1), 0.5, _BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, _BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elems.append(st)
        elems.append(Spacer(1, 10))

        # Entry zone / Analyst target / Stop loss
        ez     = tr.get("entry_zone", [])
        ez_low = ez[0] if len(ez) > 0 else None
        ez_hi  = ez[1] if len(ez) > 1 else None
        target = tr.get("target_price")
        stop   = tr.get("stop_loss")

        def _price_cell(label, text, fg, bg):
            return [
                Paragraph(label, s["CardLabel"]),
                Paragraph(
                    f'<font color="#{fg}"><b>{text}</b></font>',
                    ParagraphStyle("_pv", parent=s["Normal"], fontSize=13,
                                   fontName="Helvetica-Bold", alignment=TA_CENTER)
                )
            ]

        ez_text  = f"{cur}{_fmt(ez_low)} - {cur}{_fmt(ez_hi)}" if ez_low and ez_hi else "N/A"
        tgt_text = f"{cur}{_fmt(target, decimals=0)}" if target else "N/A"
        stp_text = f"{cur}{_fmt(stop)}"               if stop   else "N/A"

        tz_data = [[
            _price_cell("ENTRY ZONE",      ez_text,  "1e40af", "eff6ff"),
            _price_cell("ANALYST TARGET",  tgt_text, "1e40af", "eff6ff"),
            _price_cell("STOP LOSS",       stp_text, "dc2626", "fef2f2"),
        ]]
        tzt = Table(tz_data, colWidths=[PAGE_W / 3] * 3)
        tzt.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND",    (0, 0), (1, -1),  _BLUE_BG),
            ("BACKGROUND",    (2, 0), (2, -1),  _RED_BG),
            ("BOX",           (0, 0), (1, -1),  0.5, _BLUE_LIGHT),
            ("BOX",           (2, 0), (2, -1),  0.5, _RED),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elems.append(tzt)
        elems.append(Spacer(1, 10))

        # Key risks / Key catalysts
        key_risks      = risk.get("key_risks") or []
        key_catalysts  = risk.get("key_catalysts") or []
        if key_risks or key_catalysts:
            risk_text = "\n".join(f"  * {r}" for r in key_risks)      or "  —"
            cat_text  = "\n".join(f"  * {c}" for c in key_catalysts)  or "  —"
            rct = Table(
                [[Paragraph(f"Key Risks\n{risk_text}", s["BodyLeft"]),
                  Paragraph(f"Key Catalysts\n{cat_text}", s["BodyLeft"])]],
                colWidths=[PAGE_W / 2, PAGE_W / 2],
            )
            rct.setStyle(TableStyle([
                ("VALIGN",       (0, 0), (-1, -1), "TOP"),
                ("BOX",          (0, 0), (0, -1),  0.5, _RED),
                ("BOX",          (1, 0), (1, -1),  0.5, _GREEN),
                ("BACKGROUND",   (0, 0), (0, -1),  _RED_BG),
                ("BACKGROUND",   (1, 0), (1, -1),  _GREEN_BG),
                ("LEFTPADDING",  (0, 0), (-1, -1), 8),
                ("TOPPADDING",   (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
            ]))
            elems.append(rct)
            elems.append(Spacer(1, 6))

        return elems

    # ── DEEP FINANCIAL ANALYSIS ───────────────────────────────────────────────

    def _deep_financial_analysis(self, d: Dict) -> List:
        s    = self.styles
        dfa  = _get(d, "fundamentals", "details", "deep_financial_analysis") or {}
        bf   = _get(d, "fundamentals", "details", "basic_fundamentals") or {}
        cf   = _get(d, "cashflow", "details") or {}
        cur  = _cur(d)

        elems = _section_hdr("Deep Financial Analysis  (10 Years)", s)

        # Revenue Analysis
        rev_trend = _get(dfa, "income_statement_trends", "total_revenue") or {}
        rev_vals  = rev_trend.get("values", [])
        rev_latest= rev_vals[-1] if rev_vals else bf.get("revenue")

        gm       = dfa.get("growth_metrics", {}) or {}
        rev_g    = gm.get("revenue_growth", {}) or {}
        earn_g   = gm.get("earnings_growth", {}) or {}
        yoy_rev  = rev_g.get("yoy_growth")
        cagr_3y  = rev_g.get("cagr_3y")
        cagr_5y  = rev_g.get("cagr_5y")

        mar = dfa.get("margins_and_efficiency", {}) or {}
        gm_v = _get(mar, "gross_margin",     "latest")
        om_v = _get(mar, "operating_margin", "latest")
        nm_v = _get(mar, "net_margin",       "latest")

        rev_rows = []
        if rev_latest is not None: rev_rows.append(("Latest Revenue",  _cr(rev_latest)))
        if yoy_rev    is not None: rev_rows.append(("YoY Growth",      _pct(yoy_rev)))
        if cagr_3y    is not None: rev_rows.append(("3Y CAGR",         _pct(cagr_3y)))
        if cagr_5y    is not None: rev_rows.append(("5Y CAGR",         _pct(cagr_5y)))

        earn_yoy  = earn_g.get("yoy_growth")
        earn_c3   = earn_g.get("cagr_3y")
        grow_rows = []
        if earn_yoy is not None: grow_rows.append(("Earnings YoY",     _pct(earn_yoy)))
        if earn_c3  is not None: grow_rows.append(("Earnings 3Y CAGR", _pct(earn_c3)))
        if gm_v     is not None: grow_rows.append(("Gross Margin",     _pct(gm_v)))
        if om_v     is not None: grow_rows.append(("Operating Margin", _pct(om_v)))
        if nm_v     is not None: grow_rows.append(("Net Margin",       _pct(nm_v)))

        if rev_rows or grow_rows:
            cell_w = PAGE_W / 2
            two = [[
                ([Paragraph("Revenue Analysis", s["SubHeader"])] +
                 [_kv_table(rev_rows, col_widths=[1.8*inch, 1.0*inch])] if rev_rows else
                 [Paragraph("Revenue Analysis", s["SubHeader"]), Paragraph("N/A", s["Small"])]),
                ([Paragraph("Growth Metrics", s["SubHeader"])] +
                 [_kv_table(grow_rows, col_widths=[1.8*inch, 1.0*inch])] if grow_rows else
                 [Paragraph("Growth Metrics", s["SubHeader"]), Paragraph("N/A", s["Small"])]),
            ]]
            tt = Table(two, colWidths=[cell_w, cell_w])
            tt.setStyle(TableStyle([
                ("VALIGN",      (0,0), (-1,-1), "TOP"),
                ("LEFTPADDING", (0,0), (-1,-1), 4),
            ]))
            elems.append(tt)
            elems.append(Spacer(1, 8))

        # Key Financial Ratios
        fr = dfa.get("financial_ratios", {}) or {}

        def _r_latest(key):   return _get(fr, key, "latest")
        def _r_trend(key):
            vals = _get(fr, key, "values")
            if vals and len(vals) >= 2:
                return "increasing" if vals[-1] > vals[-2] else "decreasing"
            return _get(fr, key, "trend") or ""

        ratio_defs = [
            ("ROE",               "roe",               True),
            ("ROA",               "roa",               True),
            ("Asset Turnover",    "asset_turnover",     False),
            ("Debt to Equity",    "debt_to_equity",     False),
            ("Debt to Assets",    "debt_to_assets",     False),
            ("Current Ratio",     "current_ratio",      False),
            ("Cash Ratio",        "cash_ratio",         False),
            ("Interest Coverage", "interest_coverage",  False),
            ("Quick Ratio",       "quick_ratio",        False),
            ("FCF Margin",        "fcf_margin",         True),
        ]

        ratio_rows = []
        for label, key, is_pct_ratio in ratio_defs:
            v = _r_latest(key)
            if v is None:
                continue
            vf = float(v)
            display = f"{vf * 100:.2f}%" if is_pct_ratio and abs(vf) <= 2 else f"{vf:.2f}"
            ratio_rows.append([label, display, _r_trend(key)])

        # FCF from cashflow node
        # fcf_latest = cf.get("free_cash_flow")
        # if fcf_latest:
        #     ratio_rows.append(["FCF (Latest)", _cr(fcf_latest), cf.get("ocf_trend", "")])
        # fcf_margin = cf.get("fcf_margin")
        # if fcf_margin is not None:
        #     ratio_rows.append(["FCF Margin", f"{fcf_margin * 100:.1f}%", ""])

        if ratio_rows:
            elems.append(Paragraph("Key Financial Ratios", s["SubHeader"]))
            rt = Table(ratio_rows, colWidths=[2.4*inch, 1.4*inch, 2.2*inch])
            rt.setStyle(TableStyle([
                ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE",      (0, 0), (-1, -1), 9),
                ("ALIGN",         (1, 0), (1, -1), "RIGHT"),
                ("ROWBACKGROUNDS",(0, 0), (-1, -1), [_GRAY_LIGHT, _WHITE]),
                ("GRID",          (0, 0), (-1, -1), 0.5, _BORDER),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ]))
            elems.append(rt)
            elems.append(Spacer(1, 6))

        # Balance sheet strength
        bss   = _get(dfa, "balance_sheet_strength") or {}
        bss_s = _get(bss, "overall_balance_sheet_score", "score")
        bss_g = _get(bss, "overall_balance_sheet_score", "grade")
        ic_v  = _get(bss, "interest_coverage", "latest")
        cash_adq = _get(bss, "cash_position", "adequacy_score")

        bss_rows = []
        if bss_s:    bss_rows.append(("Balance Sheet Score", f"{_fmt(bss_s, decimals=0)}/100"))
        if bss_g:    bss_rows.append(("Balance Sheet Grade",  str(bss_g)))
        if ic_v:     bss_rows.append(("Interest Coverage",    f"{_fmt(ic_v)}x"))
        if cash_adq: bss_rows.append(("Cash Adequacy",        str(cash_adq).title()))
        if bss_rows:
            elems.append(Paragraph("Balance Sheet Strength", s["SubHeader"]))
            elems.append(_kv_table(bss_rows))
            elems.append(Spacer(1, 6))

        return elems

    # ── EARNINGS QUALITY ──────────────────────────────────────────────────────

    def _earnings_quality(self, d: Dict) -> List:
        s   = self.styles
        dfa = _get(d, "fundamentals", "details", "deep_financial_analysis") or {}
        eq  = dfa.get("earnings_quality", {}) or {}
        oqs = eq.get("overall_quality_score", {}) or {}
        score = oqs.get("score")
        grade = oqs.get("grade", "")
        if score is None and not grade:
            return []

        elems = _section_hdr("Earnings Quality & Balance Sheet Forensics", s)
        elems.append(Paragraph("Overall Earnings Quality", s["SubHeader"]))

        rows = []
        if score is not None: rows.append(("Score",               f"{_fmt(score, decimals=1)}/100"))
        if grade:             rows.append(("Grade",               grade))

        cfo_ni  = eq.get("cfo_to_net_income", {}) or {}
        cfo_avg = cfo_ni.get("average")
        cfo_q   = cfo_ni.get("quality_score", "")
        if cfo_avg is not None: rows.append(("CFO/Net Income avg", f"{_fmt(cfo_avg)}"))
        if cfo_q:               rows.append(("CFO Quality",        str(cfo_q).title()))

        rev_q = eq.get("revenue_quality", {}) or {}
        rev_qs = rev_q.get("quality_score", "")
        rev_cs = rev_q.get("consistency_score", "")
        if rev_qs: rows.append(("Revenue Quality",     str(rev_qs).title()))
        if rev_cs: rows.append(("Revenue Consistency", str(rev_cs).title()))

        manip = eq.get("manipulation_indicators", {}) or {}
        risk  = _get(manip, "overall_risk_score", "risk_level") or ""
        if risk: rows.append(("Manipulation Risk",  str(risk).title()))

        if rows:
            elems.append(_kv_table(rows))
        elems.append(Spacer(1, 6))
        return elems

    # ── PEER ANALYSIS ─────────────────────────────────────────────────────────

    def _peer_analysis(self, d: Dict) -> List:
        s     = self.styles
        pa    = _get(d, "peer_analysis", "details") or {}
        tgt   = pa.get("target_metrics", {}) or {}
        pm    = pa.get("peer_metrics", {}) or {}
        vm    = pa.get("valuation_metrics", {}) or {}
        peers = pa.get("peers_identified", []) or []
        rel   = pa.get("relative_position", "")

        if not pm:
            return []

        elems = _section_hdr(f"Peer Valuation Analysis  (vs {', '.join(peers[:4])})", s)
        summary = _get(d, "peer_analysis", "summary") or ""
        if summary:
            elems.append(Paragraph(str(summary)[:300], s["Body"]))
            elems.append(Spacer(1, 6))

        metric_keys = [
            ("trailing_pe",    "P/E (TTM)"),
            ("forward_pe",     "P/E (Fwd)"),
            ("price_to_book",  "P/B"),
            ("price_to_sales", "P/S"),
            ("ev_to_ebitda",   "EV/EBITDA"),
            ("dividend_yield", "Div Yield"),
            ("beta",           "Beta"),
        ]
        header = ["Metric", d.get("ticker", "Target")] + peers[:3] + ["Position"]
        rows   = [header]
        for key, label in metric_keys:
            tv = tgt.get(key)
            row = [label, _fmt(tv) if tv is not None else "N/A"]
            for peer in peers[:3]:
                pv = _get(pm, peer, key)
                row.append(_fmt(pv) if pv is not None else "N/A")
            pos = _get(vm, key, "relative_position") or ""
            row.append(pos)
            rows.append(row)

        ncols = len(rows[0])
        cw    = [1.4*inch] + [0.85*inch] * (ncols - 2) + [1.15*inch]
        pt    = Table(rows, colWidths=cw)
        pt.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  _BLUE),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  _WHITE),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_WHITE, _GRAY_LIGHT]),
            ("GRID",          (0, 0), (-1, -1), 0.5, _BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ]))
        elems.append(pt)
        if rel:
            elems.append(Spacer(1, 4))
            elems.append(Paragraph(f"Overall Valuation Position: <b>{rel}</b>", s["BodyLeft"]))
        elems.append(Spacer(1, 6))
        return elems

    # ── GOVERNANCE ────────────────────────────────────────────────────────────

    def _governance(self, d: Dict) -> List:
        s   = self.styles
        gov = _get(d, "fundamentals", "details", "governance_analysis") or {}
        if not gov:
            return []

        score     = gov.get("governance_score")
        grade     = gov.get("governance_grade", "")
        metrics   = gov.get("metrics", {}) or {}
        red_flags = gov.get("red_flags", []) or []
        recs      = gov.get("recommendations", []) or []

        elems = _section_hdr("Governance Analysis", s)
        rows  = []
        if score is not None: rows.append(("Governance Score",      f"{score}/100"))
        if grade:             rows.append(("Governance Grade",      grade))
        promo = metrics.get("promoter_holding_pct")
        inst  = metrics.get("institutional_holding_pct")
        audch = metrics.get("auditor_changes_3yr")
        if promo is not None: rows.append(("Promoter Holding",       f"{_fmt(promo)}%"))
        if inst  is not None: rows.append(("Institutional Holding",  f"{_fmt(inst)}%"))
        if audch is not None: rows.append(("Auditor Changes (3Y)",   str(audch)))

        if rows:
            elems.append(_kv_table(rows))
            elems.append(Spacer(1, 4))

        if red_flags:
            elems.append(Paragraph("Red Flags", s["SubHeader"]))
            items = [f"{rf.get('description','?')}  (Severity: {rf.get('severity','?')})" for rf in red_flags]
            elems.append(_bullets(items, s["BodyLeft"]))

        if recs:
            elems.append(Paragraph("Recommendations", s["SubHeader"]))
            elems.append(_bullets([str(r) for r in recs], s["BodyLeft"]))

        elems.append(Spacer(1, 6))
        return elems

    # ── ANALYST RECOMMENDATIONS & SENTIMENT ──────────────────────────────────

    def _analyst_section(self, d: Dict) -> List:
        s      = self.styles
        ar_det = _get(d, "analyst_recommendations", "details") or {}
        tp     = ar_det.get("target_prices", {}) or {}
        cs     = ar_det.get("recommendation_summary", {}) or {}
        ca     = ar_det.get("consensus_analysis", {}) or {}
        dist   = ca.get("recommendation_distribution", {}) or {}
        ns_det = _get(d, "news_sentiment", "details") or {}
        cur    = _cur(d)

        elems = _section_hdr("Analyst Recommendations & Market Sentiment", s)

        rows = []
        consensus  = cs.get("consensus")
        n_analysts = cs.get("analyst_count")
        if consensus:   rows.append(("Analyst Consensus",    str(consensus).title()))
        if n_analysts:  rows.append(("Number of Analysts",   str(n_analysts)))

        mean_tp = tp.get("mean")
        high_tp = tp.get("high")
        low_tp  = tp.get("low")
        if mean_tp: rows.append(("Mean Price Target",    f"{cur}{_fmt(mean_tp, decimals=0)}"))
        if high_tp: rows.append(("High Target",          f"{cur}{_fmt(high_tp, decimals=0)}"))
        if low_tp:  rows.append(("Low Target",           f"{cur}{_fmt(low_tp,  decimals=0)}"))

        impl_ret    = ca.get("implied_return")
        sentiment_s = ca.get("price_sentiment", "")
        agreement   = ca.get("analyst_agreement", "")
        if impl_ret  is not None: rows.append(("Implied Return",   f"{_fmt(impl_ret, decimals=1)}%"))
        if sentiment_s:           rows.append(("Price Sentiment",   sentiment_s))
        if agreement:             rows.append(("Analyst Agreement", agreement))

        buy_pct  = dist.get("buy_percentage")
        hold_pct = dist.get("hold_percentage")
        sell_pct = dist.get("sell_percentage")
        if buy_pct  is not None: rows.append(("Buy %",  f"{buy_pct}%"))
        if hold_pct is not None: rows.append(("Hold %", f"{hold_pct}%"))
        if sell_pct is not None: rows.append(("Sell %", f"{sell_pct}%"))

        # Sentiment data - paths confirmed from report_sample.json
        # news_sentiment.details.score, .professional_sentiment
        # news_sentiment.details.valuepickr_analysis.sentiment_score / sentiment_label
        ns_score = ns_det.get("score") or ns_det.get("news_sentiment")
        ns_label = ns_det.get("professional_sentiment", "")
        vp_score = _get(ns_det, "valuepickr_analysis", "sentiment_score")
        vp_label = _get(ns_det, "valuepickr_analysis", "sentiment_label")
        conf_ar  = _get(d, "analyst_recommendations", "confidence")

        if ns_score is not None: rows.append(("News Sentiment Score",    f"{_fmt(ns_score)}"))
        if ns_label:             rows.append(("News Sentiment",          str(ns_label)))
        if vp_score is not None: rows.append(("ValuePickr Score",        f"{_fmt(vp_score)}"))
        if vp_label:             rows.append(("ValuePickr Sentiment",    str(vp_label).title()))
        if conf_ar  is not None:
            rows.append(("Analyst Data Confidence", f"{int(float(conf_ar) * 100)}%"))

        if rows:
            elems.append(_kv_table(rows))

        # Recent news headlines
        headlines = ns_det.get("headline_analyses") or ns_det.get("headlines") or []
        if headlines:
            elems.append(Spacer(1, 6))
            elems.append(Paragraph("Recent News Headlines", s["SubHeader"]))
            for h in headlines[:5]:
                title  = h.get("headline") or h.get("title", "")
                sent   = h.get("sentiment", "")
                dated  = (h.get("formatted_date") or str(h.get("published_at", ""))[:10])
                source = h.get("source", "")
                if title:
                    elems.append(Paragraph(
                        f"[{sent}]  {title[:110]}   {dated}  {source}",
                        s["Small"]
                    ))

        elems.append(Spacer(1, 6))
        return elems

    # ── SECTOR & MACRO ────────────────────────────────────────────────────────

    def _sector_macro(self, d: Dict) -> List:
        s  = self.styles
        sm = _get(d, "sector_macro", "details") or {}
        sr = _get(d, "sector_rotation", "details") or {}

        sector       = sm.get("sector", "")
        industry     = sm.get("industry", "")
        sec_outlook  = sm.get("sector_outlook", "")
        macro_risks  = sm.get("macro_risks", []) or []
        rot_signal   = _get(sr, "recommendations", "rotation_signal") or ""
        sec_phase    = _get(sr, "sector_performance_summary", "current_phase") or ""
        rot_insights = sr.get("key_insights") or []

        if not sector:
            return []

        elems = _section_hdr("Sector & Macro Analysis", s)

        rows = []
        if sector:      rows.append(("Sector",          sector))
        if industry:    rows.append(("Industry",        industry))
        if sec_outlook: rows.append(("Sector Outlook",  sec_outlook.title()))
        if rot_signal:  rows.append(("Rotation Signal", rot_signal))
        if sec_phase:   rows.append(("Market Phase",    sec_phase))

        if rows:
            elems.append(_kv_table(rows))
            elems.append(Spacer(1, 4))

        if macro_risks:
            elems.append(Paragraph("Macro Risks", s["SubHeader"]))
            elems.append(_bullets([str(r) for r in macro_risks], s["BodyLeft"]))

        if rot_insights:
            elems.append(Paragraph("Sector Rotation Insights", s["SubHeader"]))
            elems.append(_bullets([str(i) for i in rot_insights], s["BodyLeft"]))

        elems.append(Spacer(1, 6))
        return elems

    # ── APPENDIX ─────────────────────────────────────────────────────────────

    def _appendix(self, d: Dict) -> List:
        s      = self.styles
        ticker = d.get("ticker", "")
        return [
            PageBreak(),
            Paragraph("Appendix", s["SectionHeader"]),
            HRFlowable(width="100%", thickness=0.75, color=_BLUE),
            Spacer(1, 8),
            Paragraph("Methodology", s["SubHeader"]),
            Paragraph(
                "This report was generated by EquiSense AI's proprietary analysis engine, combining "
                "fundamental analysis (DCF valuation, financial ratios, peer comparison), "
                "technical analysis (indicators, chart patterns), "
                "sentiment analysis (news, community), and sector rotation signals.",
                s["Body"],
            ),
            Spacer(1, 6),
            Paragraph("Data Sources", s["SubHeader"]),
            _bullets([
                "Yahoo Finance - price, volume and fundamental data",
                "BSE / NSE - Indian market filings and shareholding data",
                "SEC Edgar - regulatory filings for US stocks",
                "ValuePickr - Indian investor community sentiment",
                "News APIs - real-time news sentiment analysis",
            ], s["BodyLeft"]),
            Spacer(1, 10),
            HRFlowable(width="100%", thickness=0.5, color=_BORDER),
            Spacer(1, 4),
            Paragraph(
                f"Report generated by EquiSense AI on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}  "
                f"|  Ticker: {ticker}  |  research@equisense.ai",
                s["Disclaimer"],
            ),
            Paragraph(
                "This report is for informational purposes only. It does not constitute financial advice. "
                "Always consult a qualified financial advisor before making investment decisions.",
                s["Disclaimer"],
            ),
        ]


# ── Backwards-compatible public API ──────────────────────────────────────────

@dataclass
class ReportSection:
    title: str
    content: str
    data: Optional[Dict] = None
    chart_data: Optional[Dict] = None
    include_chart: bool = False


@dataclass
class ReportMetadata:
    ticker: str
    company_name: str
    report_date: datetime
    analyst: str = "EquiSense AI"
    report_type: str = "Investment Research Report"


_report_generator: Optional[PDFReportGenerator] = None


def get_report_generator() -> PDFReportGenerator:
    global _report_generator
    if _report_generator is None:
        _report_generator = PDFReportGenerator()
    return _report_generator


def generate_pdf_report(report_data: Dict[str, Any]) -> io.BytesIO:
    """Top-level entry point imported by main.py."""
    return get_report_generator().generate_report(report_data)
