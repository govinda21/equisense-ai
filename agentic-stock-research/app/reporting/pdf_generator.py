"""
PDF report generation system for EquiSense AI
Generates professional investment research reports matching the UI output.
"""

import io
import base64
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor, black, white, Color
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, ListFlowable, ListItem, KeepTogether,
    )
    from reportlab.platypus.flowables import HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics import renderPDF
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # ── Unicode font registration ──────────────────────────────────────────────
    # ReportLab's built-in Type1 fonts (Helvetica, Times-Roman) use Latin-1
    # encoding. They CANNOT render U+20B9 (Indian Rupee ₹) and output ■ instead.
    #
    # We need a TTF with full Unicode coverage.  Resolution order:
    #   1. Project-local: assets/fonts/DejaVuSans.ttf beside this file
    #   2. Linux system:  /usr/share/fonts/truetype/dejavu/
    #   3. macOS Homebrew: brew install font-dejavu  →  /opt/homebrew/share/fonts/
    #   4. One-time download from GitHub → ~/.cache/equisense/fonts/
    #   5. FALLBACK: _PDF_RUPEE_SYMBOL = "Rs." so no ■ ever appears
    #
    # _PDF_RUPEE_SYMBOL is used EVERYWHERE a rupee prefix is needed.
    # When the font loads: _PDF_RUPEE_SYMBOL = "₹"
    # When it cannot:     _PDF_RUPEE_SYMBOL = "Rs."

    _UNICODE_FONT      = "Helvetica"
    _UNICODE_FONT_BOLD = "Helvetica-Bold"
    _PDF_RUPEE_SYMBOL  = "Rs."   # safe fallback — overwritten to ₹ if TTF loads

    def _register_unicode_font() -> bool:
        import os, urllib.request
        _log = logging.getLogger(__name__)
        this_dir  = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.expanduser("~/.cache/equisense/fonts")
        pairs = [
            # 1. project-local
            (os.path.join(this_dir, "assets", "fonts", "DejaVuSans.ttf"),
             os.path.join(this_dir, "assets", "fonts", "DejaVuSans-Bold.ttf")),
            (os.path.join(this_dir, "fonts", "DejaVuSans.ttf"),
             os.path.join(this_dir, "fonts", "DejaVuSans-Bold.ttf")),
            # 2. Linux Debian/Ubuntu
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            # 2b. other Linux
            ("/usr/share/fonts/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
            # 3. macOS Homebrew arm64
            ("/opt/homebrew/share/fonts/dejavu-fonts/DejaVuSans.ttf",
             "/opt/homebrew/share/fonts/dejavu-fonts/DejaVuSans-Bold.ttf"),
            # 3b. macOS Homebrew x86
            ("/usr/local/share/fonts/DejaVuSans.ttf",
             "/usr/local/share/fonts/DejaVuSans-Bold.ttf"),
            # 4. download cache
            (os.path.join(cache_dir, "DejaVuSans.ttf"),
             os.path.join(cache_dir, "DejaVuSans-Bold.ttf")),
        ]
        for reg, bold in pairs:
            if os.path.exists(reg) and os.path.exists(bold):
                try:
                    pdfmetrics.registerFont(TTFont("DejaVuSans",      reg))
                    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold",  bold))
                    _log.info("PDF Unicode font registered: %s", reg)
                    return True
                except Exception as e:
                    _log.debug("Font registration failed (%s): %s", reg, e)
        # one-time download
        _BASE = "https://github.com/dejavu-fonts/dejavu-fonts/raw/master/ttf/"
        try:
            os.makedirs(cache_dir, exist_ok=True)
            reg_dst  = os.path.join(cache_dir, "DejaVuSans.ttf")
            bold_dst = os.path.join(cache_dir, "DejaVuSans-Bold.ttf")
            for url, dst in [(_BASE + "DejaVuSans.ttf", reg_dst),
                              (_BASE + "DejaVuSans-Bold.ttf", bold_dst)]:
                if not os.path.exists(dst):
                    _log.info("Downloading Unicode font: %s", url)
                    urllib.request.urlretrieve(url, dst)
            pdfmetrics.registerFont(TTFont("DejaVuSans",      reg_dst))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold",  bold_dst))
            _log.info("PDF Unicode font registered from download cache.")
            return True
        except Exception as e:
            _log.warning(
                "Unicode font unavailable (%s). PDF will show 'Rs.' instead of ₹. "
                "Quick fix: brew install font-dejavu (macOS) or "
                "place DejaVuSans.ttf + DejaVuSans-Bold.ttf in %s/assets/fonts/",
                e, this_dir,
            )
            return False

    if _register_unicode_font():
        _UNICODE_FONT      = "DejaVuSans"
        _UNICODE_FONT_BOLD = "DejaVuSans-Bold"
        _PDF_RUPEE_SYMBOL  = "₹"

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    _UNICODE_FONT      = "Helvetica"
    _UNICODE_FONT_BOLD = "Helvetica-Bold"
    _PDF_RUPEE_SYMBOL  = "Rs."
    logging.warning("ReportLab not available. PDF generation will be disabled.")

logger = logging.getLogger(__name__)

# ─── Colour palette (matches UI) ───────────────────────────────────────────
_BLUE      = HexColor("#1e40af")
_BLUE_LIGHT = HexColor("#3b82f6")
_GREEN     = HexColor("#16a34a")
_RED       = HexColor("#dc2626")
_ORANGE    = HexColor("#d97706")
_GRAY_DARK  = HexColor("#374151")
_GRAY_MID   = HexColor("#6b7280")
_GRAY_LIGHT = HexColor("#f3f4f6")
_BORDER    = HexColor("#e5e7eb")


# ─── Dataclasses ────────────────────────────────────────────────────────────

@dataclass
class ReportSection:
    title: str
    content: str
    data: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None
    include_chart: bool = False


@dataclass
class ReportMetadata:
    ticker: str
    company_name: str
    report_date: datetime
    analyst: str = "EquiSense AI"
    report_type: str = "Investment Research Report"
    disclaimer: str = (
        "This report is for informational purposes only and should not be "
        "considered as investment advice. Past performance does not guarantee future results."
    )


# ─── Helpers ────────────────────────────────────────────────────────────────

def _fmt(value: Any, prefix: str = "", suffix: str = "", decimals: int = 2) -> str:
    """Safe numeric formatter."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
        return f"{prefix}{v:,.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _grade_color(grade: str) -> Color:
    g = str(grade).upper()
    if g.startswith("A"):
        return _GREEN
    if g.startswith("B"):
        return _BLUE_LIGHT
    if g.startswith("C"):
        return _ORANGE
    return _RED


def _action_color(action: str) -> Color:
    a = str(action).upper()
    if "BUY" in a or "STRONG" in a:
        return _GREEN
    if "SELL" in a:
        return _RED
    return _ORANGE


def _bullet_list(items: List[str], style) -> ListFlowable:
    """Create a properly formatted bullet list."""
    return ListFlowable(
        [ListItem(Paragraph(item, style), leftIndent=12) for item in items if item],
        bulletType="bullet",
        start="•",
        leftIndent=18,
        spaceBefore=4,
        spaceAfter=4,
    )


def _beta_risk_label(beta: float) -> str:
    """
    Correct finance convention:
      beta < 0.5  → Defensive (very low volatility)
      0.5–0.8     → Low Volatility
      0.8–1.2     → Market-like
      1.2–1.5     → Moderately High Volatility
      > 1.5       → High Volatility
    A bank with beta 0.36 is DEFENSIVE, not High Risk.
    """
    if beta < 0.5:
        return "Defensive (Low Volatility)"
    if beta < 0.8:
        return "Low Volatility"
    if beta < 1.2:
        return "Market-like"
    if beta < 1.5:
        return "Moderately High Volatility"
    return "High Volatility"


# ── Known Financial Services tickers (fallback when sector field is empty) ───
# yfinance sometimes returns an empty sector for NBFCs and smaller financials.
# Rather than guessing from sector strings alone, we maintain a known-good list.
# Extend this list as new tickers are added to the coverage universe.
_KNOWN_FINANCIAL_TICKERS = frozenset({
    # Indian Private Banks
    "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS",
    "BANDHANBNK.NS", "IDFCFIRSTB.NS", "YESBANK.NS", "FEDERALBNK.NS", "RBLBANK.NS",
    # Indian Public Banks
    "SBIN.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS",
    "BANKINDIA.NS", "UCOBANK.NS", "CENTRALBK.NS", "INDIANB.NS",
    # Indian NBFCs
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS",
    "MANAPPURAM.NS", "M&MFIN.NS", "SHRIRAMFIN.NS", "LICHSGFIN.NS",
    "RECLTD.NS", "PFC.NS", "IRFC.NS",
    # Indian Insurance
    "SBILIFE.NS", "HDFCLIFE.NS", "ICICIPRULI.NS", "LICI.NS",
    "GICRE.NS", "NIACL.NS",
})


def _resolve_sector(d: Dict[str, Any]) -> str:
    """
    Robustly resolve the sector string from the report data dict.

    yfinance sometimes returns an empty sector at the top level (common for NBFCs
    and smaller Indian financials).  We try a cascade of nested paths before
    falling back to an empty string.  This single function is used by every
    section that needs to determine whether a company is Financial Services,
    so the logic is consistent and maintained in one place.
    """
    # 1. Top-level field (most common)
    s = str(d.get("sector") or "").strip()
    if s:
        return s
    # 2. valuation.details.inputs (valuation.py always records sector in inputs)
    val_inputs = (d.get("valuation") or {}).get("details", {}).get("inputs", {}) or {}
    s = str(val_inputs.get("sector") or "").strip()
    if s:
        return s
    # 3. Nested fundamentals paths
    for path in [
        lambda: (d.get("fundamentals") or {}).get("details", {}).get("basic_fundamentals", {}).get("sector"),
        lambda: (d.get("peer_analysis") or {}).get("details", {}).get("sector"),
        lambda: (d.get("sector_macro") or {}).get("details", {}).get("sector"),
        lambda: (d.get("comprehensive_fundamentals") or {}).get("sector"),
    ]:
        try:
            s = str(path() or "").strip()
            if s:
                return s
        except Exception:
            pass
    return ""


def _is_financial_sector(d: Dict[str, Any]) -> bool:
    """
    Return True if this report is for a Financial Services company.

    Uses three independent signals — any one is sufficient:
      1. Sector string (from _resolve_sector) contains financial/bank/insurance/nbfc
      2. valuation.details.primary_model == "excess_returns"  (set by valuation.py)
      3. Ticker is in the known financial tickers list
    """
    ticker  = str(d.get("ticker") or "").strip().upper()
    sector  = _resolve_sector(d).lower()
    primary = str((d.get("valuation") or {}).get("details", {}).get("primary_model") or "").lower()

    return (
        any(kw in sector for kw in ("financial", "bank", "insurance", "nbfc", "credit"))
        or primary == "excess_returns"
        or ticker in _KNOWN_FINANCIAL_TICKERS
        or any(ticker.startswith(pfx) for pfx in
               ("HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN.",
                "BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "MUTHOOTFIN"))
    )


def _f_safe(v: Any) -> Optional[float]:
    try:
        x = float(v)
        return None if x != x else x
    except Exception:
        return None


def _sanitize_report(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pre-flight sanity checks run BEFORE any section renders.
    Catches contradictions that originate upstream in the LLM synthesis
    or data-fetch layer and corrects them so the PDF is internally consistent.

    Rules applied:
    1. current_price: resolve from multiple locations into one canonical field.
    2. analyst_target: resolve from nested details dict.
    3. expected_return_pct: recompute from (target - price) / price.
       If LLM-stored value disagrees by >5pp, replace it.
    4. recommendation: if expected_return >= 20% and action == HOLD, upgrade to BUY.
       If expected_return <= -10% and action == BUY, downgrade to SELL.
    5. executive_summary: scrub known factually wrong phrases for Financial Services tickers.
    6. entry_zone: ensure low < high; swap if reversed, nullify if clearly bogus.
    7. dcf_applicable flag: if sector is Financial Services, force to False so the
       PDF never prints "DCF not applicable" as if the company is loss-making.
    8. beta: store corrected risk label.
    """
    d = dict(d)  # shallow copy — don't mutate the original

    # ── 1. Canonical current price ─────────────────────────────────────────
    # Priority: analyst_recommendations is the most reliable source because it uses
    # the same fetch_info() / yahoo_client.get_info() code path as the report header.
    # valuation.details.inputs.current_price comes from a direct yf.Ticker().info
    # call inside compute_valuation._run() which can return a different (stale,
    # split-adjusted, or pre-merger) value — this was the root cause of the
    # HDFCBANK.NS price split (header showed 1857, valuation table showed 857).
    ar_block = (d.get("analyst_recommendations") or {})
    ar_det   = ar_block.get("details") or ar_block  # handle both wrapped and unwrapped
    price = (
        _f_safe(ar_det.get("current_price"))                                       # ← canonical
        or _f_safe(d.get("currentPrice"))
        or _f_safe(d.get("current_price"))
        or _f_safe((d.get("comprehensive_fundamentals") or {}).get("current_price"))
        # valuation inputs price is last-resort only — it may be stale
        or _f_safe((d.get("valuation") or {}).get("details", {}).get("inputs", {}).get("current_price"))
    )
    if price:
        d["_price"] = price  # internal canonical key used by renderers

    # ── 2. Canonical analyst target ────────────────────────────────────────
    ar_details = (d.get("analyst_recommendations") or {}).get("details", {}) or {}
    analyst_target = (
        _f_safe(ar_details.get("target_prices", {}).get("mean"))
        or _f_safe(d.get("analyst_target"))
        or _f_safe((d.get("decision") or {}).get("price_target_12m"))
        or _f_safe((d.get("comprehensive_fundamentals") or {}).get("target_price"))
    )
    if analyst_target:
        d["_analyst_target"] = analyst_target

    # ── 3. Recompute expected return ───────────────────────────────────────
    decision = dict(d.get("decision") or {})
    stored_return_pct = _f_safe(decision.get("expected_return_pct"))

    if price and analyst_target and analyst_target > 0:
        recomputed_return_pct = (analyst_target - price) / price * 100
        # If stored value is mathematically impossible (wrong sign, or >5pp off), replace it
        if stored_return_pct is None or abs(recomputed_return_pct - stored_return_pct) > 5:
            decision["expected_return_pct"] = round(recomputed_return_pct, 1)
            decision["_return_recomputed"] = True
        d["decision"] = decision

    final_return_pct = _f_safe(decision.get("expected_return_pct"))

    # ── 4. Recommendation consistency ─────────────────────────────────────
    action = str(decision.get("action") or "").strip()
    if final_return_pct is not None and action:
        action_upper = action.upper()
        # A 12%+ upside should never be HOLD — upgrade to BUY.
        # (Indian market convention: analyst consensus treats >10–12% as a Buy signal)
        if final_return_pct >= 12 and action_upper in ("HOLD", "WEAK HOLD"):
            decision["action"] = "Buy"
            decision["_action_upgraded"] = f"Upgraded from {action} — {final_return_pct:.1f}% upside inconsistent with Hold"
        # A -10%+ downside should never be BUY — downgrade to SELL
        elif final_return_pct <= -10 and action_upper in ("BUY", "STRONG BUY"):
            decision["action"] = "Sell"
            decision["_action_downgraded"] = f"Downgraded from {action} — {final_return_pct:.1f}% downside inconsistent with Buy"
        d["decision"] = decision

    # ── 5. Executive summary: scrub factually wrong phrases ───────────────
    # Use the shared helper so the same sector-resolution logic applies here
    # as everywhere else in the report (empty top-level sector is common for NBFCs).
    is_financial = _is_financial_sector(d)

    WRONG_PHRASES = [
        "As a loss-making company, DCF is not applicable.",
        "As a loss-making company, DCF is not applicable",
        "loss-making company",
        "path to profitability",
    ]
    FINANCIAL_DCF_NOTE = (
        "As a Financial Services company, the standard DCF model is not applicable. "
        "Valuation uses the Excess Returns (Residual Income) method instead."
    )

    # Text fields that may contain stale action wording from the LLM
    _TEXT_FIELDS_TO_SCRUB = ["executive_summary", "thesis", "rationale", "investment_thesis"]

    # Determine final action (post rule-4 upgrade/downgrade) for contradiction scrubbing
    final_action = str(decision.get("action") or "").strip().upper()

    def _scrub_text(text: str) -> str:
        """Apply all text-level fixes: remove wrong DCF phrases, fix stale action wording,
        reconcile upside percentage so thesis doesn't quote a different number than the
        official Expected Return shown in the scorecard."""
        if not text:
            return text
        import re as _re
        # Financial Services DCF phrase replacement
        if is_financial:
            for phrase in WRONG_PHRASES:
                if phrase.lower() in text.lower():
                    text = _re.sub(_re.escape(phrase), FINANCIAL_DCF_NOTE, text, flags=_re.IGNORECASE)
        # If action was upgraded to BUY, scrub "We rate … as Hold" / "Hold with X% conviction"
        if final_action in ("BUY", "STRONG BUY"):
            text = _re.sub(r'\brate\s+\S+\s+as\s+[Hh]old\b', lambda m: m.group(0).rsplit("Hold", 1)[0] + "Buy", text)
            text = _re.sub(r'\b[Hh]old\s+with\s+(\d+)%\s+conviction\b', r'Buy with \1% conviction', text)
            text = _re.sub(r'\brecommend\s+[Hh]old\b', 'recommend Buy', text)
        # If action was downgraded to SELL, scrub stale BUY wording
        if final_action in ("SELL", "STRONG SELL"):
            text = _re.sub(r'\brate\s+\S+\s+as\s+[Bb]uy\b', lambda m: m.group(0).rsplit("Buy", 1)[0] + "Sell", text)
            text = _re.sub(r'\brecommend\s+[Bb]uy\b', 'recommend Sell', text)
        # ── Reconcile "X% upside" claims in thesis text ──────────────────
        # The LLM sometimes writes "DCF intrinsic value of X suggests Y% upside" in the
        # thesis, where Y% is the raw DCF-vs-price gap.  The official Expected Return in
        # the scorecard is based on the analyst consensus target, not DCF — these are two
        # different numbers.  We replace the raw DCF upside percentage with a note that
        # redirects readers to the DCF Intrinsic Value row in the Valuation section.
        if final_return_pct is not None:
            # Match "suggests N% upside" or "implies N% upside" where N differs from official return
            def _fix_upside(m):
                mentioned_pct = float(m.group(1))
                # If the mentioned pct is close to the official return, leave it alone
                if abs(mentioned_pct - final_return_pct) < 3:
                    return m.group(0)
                # Otherwise rewrite to avoid the conflicting figure
                return (f"suggests significant intrinsic value upside (see DCF Valuation section). "
                        f"12-month analyst consensus return: {final_return_pct:+.1f}%")
            text = _re.sub(
                r'suggests?\s+(\d+(?:\.\d+)?)%\s+upside',
                _fix_upside, text, flags=_re.IGNORECASE
            )
            text = _re.sub(
                r'implies?\s+(\d+(?:\.\d+)?)%\s+(?:potential\s+)?upside',
                _fix_upside, text, flags=_re.IGNORECASE
            )
        return text

    # Apply scrubbing to decision fields and top-level text fields
    for field in _TEXT_FIELDS_TO_SCRUB:
        if decision.get(field):
            decision[field] = _scrub_text(str(decision[field]))
        if d.get(field):
            d[field] = _scrub_text(str(d[field]))

    # Canonical exec summary pointer
    exec_summary = str(decision.get("executive_summary") or d.get("executive_summary") or "")
    if is_financial:
        for phrase in WRONG_PHRASES:
            if phrase.lower() in exec_summary.lower():
                exec_summary = exec_summary.replace(phrase, FINANCIAL_DCF_NOTE)
        decision["executive_summary"] = exec_summary
        d["executive_summary"] = exec_summary
    d["decision"] = decision

    # ── 6. Entry zone sanity check ─────────────────────────────────────────
    cf = d.get("comprehensive_fundamentals") or {}
    ez_low  = _f_safe(cf.get("entry_zone_low"))
    ez_high = _f_safe(cf.get("entry_zone_high"))
    if ez_low is not None and ez_high is not None:
        if ez_low > ez_high:
            ez_low, ez_high = ez_high, ez_low  # swap
        # Sanity: entry zone must be within 50% of current price
        if price and not (price * 0.5 <= ez_low <= price * 1.5 and price * 0.5 <= ez_high <= price * 1.5):
            ez_low = ez_high = None  # nullify — bogus data
        cf = dict(cf)
        cf["entry_zone_low"]  = ez_low
        cf["entry_zone_high"] = ez_high
        d["comprehensive_fundamentals"] = cf

    # ── 7. Beta risk label ─────────────────────────────────────────────────
    beta = (
        _f_safe(d.get("beta"))
        or _f_safe((d.get("valuation") or {}).get("details", {}).get("inputs", {}).get("beta"))
    )
    if beta is not None:
        d["_beta"] = beta
        d["_beta_risk_label"] = _beta_risk_label(beta)

    return d


def _two_col_table(rows: List[tuple], col_widths=None) -> Table:
    """Render a key/value table with alternating row shading.

    Value cells longer than ~60 characters are automatically wrapped in a
    Paragraph so ReportLab flows them across multiple lines instead of truncating.
    """
    col_widths = col_widths or [2.8 * inch, 3.2 * inch]

    # Build a minimal style for wrapping value cells (no external style registry needed)
    _val_style = ParagraphStyle(
        "TwoColValue",
        fontName=_UNICODE_FONT,
        fontSize=10,
        leading=13,
        textColor=HexColor("#374151"),
    )
    _key_style = ParagraphStyle(
        "TwoColKey",
        fontName=_UNICODE_FONT_BOLD,
        fontSize=10,
        leading=13,
        textColor=HexColor("#374151"),
    )

    # Wrap any string value longer than 55 chars in a Paragraph for auto-wrap
    processed_rows = []
    for key, val in rows:
        key_cell = Paragraph(str(key), _key_style) if len(str(key)) > 30 else str(key)
        if isinstance(val, str) and len(val) > 55:
            val_cell = Paragraph(val, _val_style)
        else:
            val_cell = val
        processed_rows.append((key_cell, val_cell))

    style = [
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME",      (0, 0), (0, -1),  _UNICODE_FONT_BOLD),
        ("FONTNAME",      (1, 0), (1, -1),  _UNICODE_FONT),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("GRID",          (0, 0), (-1, -1), 0.5, _BORDER),
    ]
    for i in range(0, len(processed_rows), 2):
        style.append(("BACKGROUND", (0, i), (-1, i), _GRAY_LIGHT))
    t = Table(processed_rows, colWidths=col_widths)
    t.setStyle(TableStyle(style))
    return t


# ─── Main generator class ───────────────────────────────────────────────────

class PDFReportGenerator:
    """Generates professional PDF reports that mirror the UI output."""

    def __init__(self):
        self.styles = None
        if PDF_AVAILABLE:
            self._initialize_styles()

    def _initialize_styles(self):
        self.styles = getSampleStyleSheet()

        def add(name, parent, **kw):
            if name not in self.styles:
                self.styles.add(ParagraphStyle(name=name, parent=self.styles[parent], **kw))

        # Use DejaVuSans for all styles — it supports ₹ (U+20B9) unlike Helvetica.
        # Fallback to Helvetica when DejaVuSans is not available (non-Linux environments).
        _uf  = _UNICODE_FONT        # "DejaVuSans"      or "Helvetica"
        _ufb = _UNICODE_FONT_BOLD   # "DejaVuSans-Bold" or "Helvetica-Bold"

        add("CustomTitle",      "Title",    fontSize=22, spaceAfter=6,  alignment=TA_CENTER, textColor=_BLUE, fontName=_ufb)
        add("ReportSubtitle",   "Normal",   fontSize=13, spaceAfter=4,  alignment=TA_CENTER, textColor=_GRAY_MID, fontName=_uf)
        add("SectionHeader",    "Heading2", fontSize=15, spaceAfter=8,  spaceBefore=18, textColor=_BLUE,      fontName=_ufb)
        add("SubsectionHeader", "Heading3", fontSize=12, spaceAfter=6,  spaceBefore=10, textColor=_GRAY_DARK, fontName=_ufb)
        add("BodyText",         "Normal",   fontSize=10, spaceAfter=4,  alignment=TA_JUSTIFY, textColor=_GRAY_DARK, leading=15, fontName=_uf)
        add("MetricLabel",      "Normal",   fontSize=10, textColor=_GRAY_MID, fontName=_uf)
        add("MetricValue",      "Normal",   fontSize=10, textColor=_GRAY_DARK, fontName=_ufb)
        add("Disclaimer",       "Normal",   fontSize=8,  spaceAfter=4,  alignment=TA_CENTER, textColor=_GRAY_MID, fontName=_uf)
        add("SmallText",        "Normal",   fontSize=9,  textColor=_GRAY_MID, fontName=_uf)
        add("GradeText",        "Normal",   fontSize=28, alignment=TA_CENTER, fontName=_ufb, textColor=_BLUE)
        add("ActionText",       "Normal",   fontSize=14, alignment=TA_CENTER, fontName=_ufb, textColor=_GREEN)
        add("TOCEntry",         "Normal",   fontSize=10, spaceAfter=3,  textColor=_GRAY_DARK, fontName=_uf)

    # ── Public API ─────────────────────────────────────────────────────────

    def generate_report(self, report_data: Dict[str, Any]) -> io.BytesIO:
        """
        Build a PDF from a raw analysis report_data dict (as returned by the graph).
        Returns an io.BytesIO positioned at position 0 — ready for StreamingResponse.
        """
        if not PDF_AVAILABLE:
            raise RuntimeError("ReportLab is not installed. Run: pip install reportlab")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=56,
            leftMargin=56,
            topMargin=56,
            bottomMargin=40,
            title=f"EquiSense Research — {report_data.get('ticker', '')}",
            author="EquiSense AI",
        )

        # Run pre-flight sanity checks — fixes contradictions before any section renders
        report_data = _sanitize_report(report_data)

        story = []
        story.extend(self._title_page(report_data))
        story.append(PageBreak())
        story.extend(self._scorecard(report_data))
        story.extend(self._investment_thesis(report_data))
        story.extend(self._key_metrics(report_data))
        story.extend(self._financials(report_data))
        story.extend(self._valuation(report_data))
        story.extend(self._technical(report_data))
        story.extend(self._risk_factors(report_data))
        story.extend(self._analyst_sentiment(report_data))
        story.extend(self._appendix(report_data))

        doc.build(story)
        buffer.seek(0)

        logger.info(f"PDF generated for {report_data.get('ticker')} ({buffer.getbuffer().nbytes:,} bytes)")
        return buffer

    # ── Sections ───────────────────────────────────────────────────────────

    def _title_page(self, d: Dict) -> List:
        s = self.styles
        ticker       = d.get("ticker", "N/A")
        company      = d.get("company_name") or d.get("companyName") or ticker
        sector       = d.get("sector", "")
        exchange     = d.get("exchange", "")
        price        = d.get("_price") or d.get("currentPrice") or d.get("current_price")
        currency_sym = _PDF_RUPEE_SYMBOL if (str(ticker).endswith(".NS") or str(ticker).endswith(".BO")) else "$"
        decision     = d.get("decision", {}) or {}
        action       = decision.get("action", d.get("recommendation", ""))
        grade        = decision.get("grade", d.get("grade", ""))
        rating       = decision.get("rating", d.get("rating", ""))

        elems = [
            Spacer(1, 0.6 * inch),
            Paragraph(company, s["CustomTitle"]),
            Paragraph(f"{ticker}  |  {sector}  |  {exchange}", s["ReportSubtitle"]),
            Spacer(1, 0.2 * inch),
            HRFlowable(width="100%", thickness=2, color=_BLUE),
            Spacer(1, 0.3 * inch),
        ]

        # Scorecard banner row
        banner_rows = []
        if price:
            banner_rows.append((f"Current Price", f"{currency_sym}{_fmt(price)}"))
        if action:
            banner_rows.append(("Recommendation", action.upper()))
        if grade:
            banner_rows.append(("Grade", str(grade).upper()))
        if rating:
            banner_rows.append(("Rating", f"{rating}/100"))

        if banner_rows:
            banner_data   = [[b[0] for b in banner_rows], [b[1] for b in banner_rows]]
            banner_widths = [6.0 * inch / len(banner_rows)] * len(banner_rows)
            banner = Table(banner_data, colWidths=banner_widths)
            banner.setStyle(TableStyle([
                ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME",      (0, 0), (-1, 0),  _UNICODE_FONT),
                ("FONTNAME",      (0, 1), (-1, 1),  _UNICODE_FONT_BOLD),
                ("FONTSIZE",      (0, 0), (-1, 0),  9),
                ("FONTSIZE",      (0, 1), (-1, 1),  16),
                ("TEXTCOLOR",     (0, 0), (-1, 0),  _GRAY_MID),
                ("TEXTCOLOR",     (0, 1), (-1, 1),  _BLUE),
                ("BACKGROUND",    (0, 0), (-1, -1), _GRAY_LIGHT),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("GRID",          (0, 0), (-1, -1), 0.5, _BORDER),
                ("ROUNDEDCORNERS", [4]),
            ]))
            elems.append(banner)
            elems.append(Spacer(1, 0.3 * inch))

        # Report metadata table
        meta_rows = [
            ("Report Date",   datetime.now().strftime("%B %d, %Y")),
            ("Analyst",       "EquiSense AI"),
            ("Report Type",   "Investment Research Report"),
        ]
        if sector:
            meta_rows.append(("Sector", sector))
        elems.append(_two_col_table(meta_rows, col_widths=[2 * inch, 3.8 * inch]))
        elems.append(Spacer(1, 0.5 * inch))
        elems.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
        elems.append(Spacer(1, 0.1 * inch))
        elems.append(Paragraph(
            "This report is for informational purposes only and should not be considered "
            "as investment advice. Past performance does not guarantee future results.",
            s["Disclaimer"],
        ))
        return elems

    def _scorecard(self, d: Dict) -> List:
        s = self.styles
        decision = d.get("decision", {}) or {}
        score    = d.get("comprehensive_score") or d.get("score") or decision.get("score")
        grade    = d.get("grade") or decision.get("grade", "") or decision.get("letter_grade", "")
        action   = (d.get("recommendation") or decision.get("action", "")).upper()
        rating   = d.get("rating") or decision.get("rating")

        # Sub-scores — also check comprehensive_fundamentals
        sub_scores   = d.get("sub_scores", {}) or d.get("scores", {}) or {}
        cf_scores    = d.get("comprehensive_fundamentals") or {}
        fundamental  = sub_scores.get("fundamental")  or d.get("fundamental_score")  or cf_scores.get("financial_health_score")
        technical    = sub_scores.get("technical")    or d.get("technical_score")
        sentiment    = sub_scores.get("sentiment")    or d.get("sentiment_score")
        valuation_sc = sub_scores.get("valuation")    or d.get("valuation_score")     or cf_scores.get("valuation_score")

        # Canonical price and targets (set by _sanitize_report)
        price          = d.get("_price")
        analyst_target = d.get("_analyst_target")
        ticker         = d.get("ticker", "")
        currency_sym   = _PDF_RUPEE_SYMBOL if (str(ticker).endswith(".NS") or str(ticker).endswith(".BO")) else "$"
        return_pct     = _f_safe(decision.get("expected_return_pct"))

        elems = [Paragraph("Investment Recommendation", s["SectionHeader"]),
                 HRFlowable(width="100%", thickness=0.5, color=_BORDER), Spacer(1, 6)]

        # ── Top banner: Current Price | Target | Expected Return | Model ───
        banner_labels, banner_values = [], []
        if price is not None:
            banner_labels.append("Current Price")
            banner_values.append(f"{currency_sym}{_fmt(price)}")
        if analyst_target is not None:
            banner_labels.append("Price Target")
            banner_values.append(f"{currency_sym}{_fmt(analyst_target, decimals=0)}")
        if return_pct is not None:
            banner_labels.append("Expected Return")
            banner_values.append(f"{return_pct:+.1f}%")
        # Valuation model — use shared helper so NBFCs/financials with empty sector are handled
        is_fin = _is_financial_sector(d)
        val_details = (d.get("valuation") or {}).get("details", {}) or {}
        cs_val_metrics = ((d.get("comprehensive_score") or d.get("scoring") or {}).get("valuation") or {}).get("key_metrics") or {}
        cf_data_sc = d.get("comprehensive_fundamentals") or {}
        if is_fin:
            er = val_details.get("models", {}).get("excess_returns", {})
            er_iv = (
                _f_safe(er.get("intrinsic_value"))
                or _f_safe(cs_val_metrics.get("intrinsic_value"))
                or _f_safe(cf_data_sc.get("intrinsic_value"))
            )
            # Inline recompute as last resort for the banner
            if not er_iv:
                _bvps = _f_safe(cf_data_sc.get("bookValue")) or _f_safe((val_details.get("inputs") or {}).get("book_value_ps"))
                _roe  = _f_safe(cf_data_sc.get("returnOnEquity")) or _f_safe((val_details.get("inputs") or {}).get("return_on_equity"))
                _ke   = _f_safe((val_details.get("inputs") or {}).get("cost_of_equity")) or _f_safe(cs_val_metrics.get("cost_of_equity")) or 0.1365
                if _bvps and _roe and _bvps > 0 and _ke > 0.025:
                    _excess = _roe - _ke
                    er_iv = round(_bvps + (_bvps * _excess) / (_ke - 0.025), 2)
            banner_labels.append("Excess Returns IV")
            banner_values.append(f"{currency_sym}{_fmt(er_iv, decimals=0)}" if er_iv and er_iv > 0 else "See Valuation")
        else:
            dcf_m = val_details.get("models", {}).get("dcf", {})
            dcf_p = _f_safe((dcf_m.get("base_case") or {}).get("intrinsic_price", {}).get("base"))
            banner_labels.append("DCF Valuation")
            banner_values.append(f"{currency_sym}{_fmt(dcf_p, decimals=0)}" if dcf_p else "N/A")

        if banner_labels:
            ncols = len(banner_labels)
            col_w = 6.0 * inch / ncols
            banner = Table([banner_labels, banner_values], colWidths=[col_w] * ncols)
            banner.setStyle(TableStyle([
                ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME",      (0, 0), (-1, 0),  _UNICODE_FONT),
                ("FONTNAME",      (0, 1), (-1, 1),  _UNICODE_FONT_BOLD),
                ("FONTSIZE",      (0, 0), (-1, 0),  9),
                ("FONTSIZE",      (0, 1), (-1, 1),  16),
                ("TEXTCOLOR",     (0, 0), (-1, 0),  _GRAY_MID),
                ("TEXTCOLOR",     (0, 1), (-1, 1),  _BLUE),
                ("BACKGROUND",    (0, 0), (-1, -1), _GRAY_LIGHT),
                ("TOPPADDING",    (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("GRID",          (0, 0), (-1, -1), 0.5, _BORDER),
            ]))
            elems.append(banner)
            elems.append(Spacer(1, 8))

        # ── Data integrity notices ─────────────────────────────────────────
        for flag_key, flag_style in [
            ("_return_recomputed",  "SmallText"),
            ("_action_upgraded",    "SmallText"),
            ("_action_downgraded",  "SmallText"),
        ]:
            msg = decision.get(flag_key)
            if msg:
                prefix = "⚠ Return recomputed from price data. " if flag_key == "_return_recomputed" else f"⚠ {msg}"
                elems.append(Paragraph(prefix, s[flag_style]))

        # ── Score table ────────────────────────────────────────────────────
        score_rows = []
        if score is not None:
            score_rows.append(("Overall Score",     f"{_fmt(score, decimals=1)} / 100"))
        if grade:
            score_rows.append(("Grade",             str(grade).upper()))
        if action:
            score_rows.append(("Recommendation",    action))
        if rating is not None:
            score_rows.append(("Rating",            f"{rating} / 100"))
        if fundamental is not None:
            score_rows.append(("Fundamental Score", f"{_fmt(fundamental, decimals=1)}"))
        if technical is not None:
            score_rows.append(("Technical Score",   f"{_fmt(technical, decimals=1)}"))
        if sentiment is not None:
            score_rows.append(("Sentiment Score",   f"{_fmt(sentiment, decimals=1)}"))
        if valuation_sc is not None:
            score_rows.append(("Valuation Score",   f"{_fmt(valuation_sc, decimals=1)}"))

        if score_rows:
            elems.append(_two_col_table(score_rows))
        elems.append(Spacer(1, 8))
        return elems

    def _investment_thesis(self, d: Dict) -> List:
        s = self.styles
        decision = d.get("decision", {}) or {}

        thesis    = (decision.get("thesis") or d.get("thesis") or d.get("investment_thesis") or "").strip()
        rationale = (decision.get("rationale") or d.get("rationale") or "").strip()
        # executive_summary: prefer decision.executive_summary (already sanitized by _sanitize_report)
        summary   = (decision.get("executive_summary") or d.get("executive_summary") or d.get("summary") or "").strip()

        bulls     = decision.get("bull_points") or d.get("bull_points") or d.get("strengths") or []
        bears     = decision.get("bear_points") or d.get("bear_points") or d.get("risks") or []
        catalysts = d.get("catalysts") or decision.get("catalysts") or []

        elems = []
        if not any([thesis, rationale, summary, bulls, bears]):
            return elems

        elems += [Paragraph("Investment Thesis", s["SectionHeader"]), HRFlowable(width="100%", thickness=0.5, color=_BORDER), Spacer(1, 6)]

        # Deduplicate: avoid printing the same sentence twice across thesis/rationale/summary.
        # The LLM sometimes embeds the same DCF-inapplicability note in both thesis and summary.
        seen_sentences: set = set()
        def _dedup_text(text: str) -> str:
            """
            Remove sentences already seen in previous text blocks.
            Also removes fragments where a long duplicate phrase appears mid-sentence
            (e.g. LLM repeats the same clause inside different sentences).
            Returns cleaned text or empty string if nothing new remains.
            """
            if not text:
                return ""
            # Split on sentence boundaries
            result_parts = []
            for sentence in text.replace(". ", ".|").replace(".\n", ".|\n").split("|"):
                stripped = sentence.strip()
                normalised = stripped.lower()
                if not normalised:
                    continue
                # Exact duplicate
                if normalised in seen_sentences:
                    continue
                # Substring duplicate: skip if this sentence is substantially contained in
                # something already seen (≥60 chars shared), OR already-seen text is in this sentence
                skip = False
                for seen in seen_sentences:
                    # If this sentence contains >60 chars already seen — it's a repeat
                    if len(seen) > 60 and seen in normalised:
                        skip = True
                        break
                    # If an already-seen sentence contains this one verbatim (short sentence reuse)
                    if len(normalised) > 40 and normalised in seen:
                        skip = True
                        break
                if skip:
                    continue
                seen_sentences.add(normalised)
                result_parts.append(stripped)
            return " ".join(result_parts).strip()

        for text in [thesis, rationale, summary]:
            cleaned = _dedup_text(text)
            if cleaned:
                elems.append(Paragraph(cleaned, s["BodyText"]))
                elems.append(Spacer(1, 4))

        if bulls:
            elems.append(Paragraph("Bull Case", s["SubsectionHeader"]))
            elems.append(_bullet_list([str(b) for b in bulls], s["BodyText"]))

        if bears:
            elems.append(Paragraph("Bear Case / Key Risks", s["SubsectionHeader"]))
            elems.append(_bullet_list([str(b) for b in bears], s["BodyText"]))

        if catalysts:
            elems.append(Paragraph("Catalysts", s["SubsectionHeader"]))
            elems.append(_bullet_list([str(c) for c in catalysts], s["BodyText"]))

        elems.append(Spacer(1, 8))
        return elems

    def _key_metrics(self, d: Dict) -> List:
        s = self.styles
        currency_sym = _PDF_RUPEE_SYMBOL if (str(d.get("ticker", "")).endswith(".NS") or str(d.get("ticker", "")).endswith(".BO")) else "$"

        # Pull metrics from wherever the graph stored them
        fi = d.get("fundamentals") or d.get("financial_data") or d.get("raw_data") or {}
        price      = d.get("currentPrice") or d.get("current_price") or fi.get("currentPrice")
        mkt_cap    = d.get("marketCap")    or fi.get("marketCap")
        pe         = d.get("trailingPE")   or fi.get("trailingPE")   or fi.get("pe_ratio")
        pb         = d.get("priceToBook")  or fi.get("priceToBook")  or fi.get("pb_ratio")
        ps         = d.get("priceToSalesTrailing12Months") or fi.get("priceToSalesTrailing12Months")
        ev_ebitda  = d.get("enterpriseToEbitda") or fi.get("enterpriseToEbitda")
        roe        = d.get("returnOnEquity")     or fi.get("returnOnEquity")
        roa        = d.get("returnOnAssets")     or fi.get("returnOnAssets")
        margins    = d.get("profitMargins")      or fi.get("profitMargins")
        div_yield  = d.get("dividendYield")      or fi.get("dividendYield")
        debt_eq    = d.get("debtToEquity")       or fi.get("debtToEquity")
        current_r  = d.get("currentRatio")       or fi.get("currentRatio")
        beta       = d.get("beta")               or fi.get("beta")
        week52_h   = d.get("fiftyTwoWeekHigh")   or fi.get("fiftyTwoWeekHigh")
        week52_l   = d.get("fiftyTwoWeekLow")    or fi.get("fiftyTwoWeekLow")

        # Use canonical price from _sanitize_report if available
        price = d.get("_price") or price

        rows = []
        if price     is not None: rows.append(("Current Price",     f"{currency_sym}{_fmt(price)}"))
        if mkt_cap   is not None:
            # Format market cap in Cr or B
            try:
                mc = float(mkt_cap)
                if currency_sym == _PDF_RUPEE_SYMBOL:
                    rows.append(("Market Cap", f"₹{mc/1e7:,.0f} Cr"))
                else:
                    rows.append(("Market Cap", f"${mc/1e9:,.2f}B"))
            except Exception:
                rows.append(("Market Cap", str(mkt_cap)))
        if pe        is not None: rows.append(("P/E Ratio",          _fmt(pe)))
        if pb        is not None: rows.append(("P/B Ratio",          _fmt(pb)))
        if ps        is not None: rows.append(("P/S Ratio",          _fmt(ps)))
        if ev_ebitda is not None: rows.append(("EV/EBITDA",          _fmt(ev_ebitda)))
        if roe       is not None: rows.append(("Return on Equity",   _fmt(roe * 100 if roe < 1 else roe, suffix="%")))
        if roa       is not None: rows.append(("Return on Assets",   _fmt(roa * 100 if roa < 1 else roa, suffix="%")))
        if margins   is not None: rows.append(("Profit Margin",      _fmt(margins * 100 if margins < 1 else margins, suffix="%")))
        if div_yield is not None: rows.append(("Dividend Yield",     _fmt(div_yield * 100 if div_yield < 1 else div_yield, suffix="%")))
        if debt_eq   is not None: rows.append(("Debt/Equity",        _fmt(debt_eq, suffix="%")))
        if current_r is not None: rows.append(("Current Ratio",      _fmt(current_r)))
        # Beta: show value AND correct volatility label (beta<1 is defensive, not "High Risk")
        beta_canonical = d.get("_beta") or beta
        if beta_canonical is not None:
            risk_label = d.get("_beta_risk_label") or _beta_risk_label(float(beta_canonical))
            rows.append(("Beta", f"{_fmt(beta_canonical)}  ({risk_label})"))
        if week52_h  is not None: rows.append(("52-Week High",       f"{currency_sym}{_fmt(week52_h)}"))
        if week52_l  is not None: rows.append(("52-Week Low",        f"{currency_sym}{_fmt(week52_l)}"))

        if not rows:
            return []

        elems = [
            Paragraph("Key Metrics", s["SectionHeader"]),
            HRFlowable(width="100%", thickness=0.5, color=_BORDER),
            Spacer(1, 6),
            _two_col_table(rows),
            Spacer(1, 8),
        ]
        return elems

    def _financials(self, d: Dict) -> List:
        s = self.styles
        deep = d.get("deep_financial_analysis") or d.get("financial_analysis") or {}
        cagr = deep.get("cagr") or deep.get("growth_rates") or {}
        income = deep.get("income_statement") or d.get("income_statement") or {}

        rev_cagr  = cagr.get("revenue_3y") or cagr.get("revenue_cagr_3y")
        pat_cagr  = cagr.get("pat_3y")     or cagr.get("net_income_cagr_3y")
        ebit_cagr = cagr.get("ebit_3y")    or cagr.get("operating_cagr_3y")

        revenues  = income.get("revenue")    or deep.get("revenues")    or []
        net_inc   = income.get("net_income") or deep.get("net_income")  or []

        rows = []
        if rev_cagr  is not None: rows.append(("Revenue CAGR (3Y)",     _fmt(rev_cagr,  suffix="%")))
        if pat_cagr  is not None: rows.append(("Net Income CAGR (3Y)",  _fmt(pat_cagr,  suffix="%")))
        if ebit_cagr is not None: rows.append(("EBIT CAGR (3Y)",        _fmt(ebit_cagr, suffix="%")))
        if revenues:
            rows.append(("Latest Revenue",   _fmt(revenues[-1] / 1e9  if revenues[-1] > 1e7 else revenues[-1],  suffix="B" if revenues[-1] > 1e7 else "")))
        if net_inc:
            rows.append(("Latest Net Income", _fmt(net_inc[-1] / 1e9   if net_inc[-1]  > 1e7 else net_inc[-1],  suffix="B" if net_inc[-1] > 1e7  else "")))

        # Also check top-level keys the graph sometimes uses
        for key, label in [
            ("revenue_growth", "Revenue Growth"),
            ("earnings_growth", "Earnings Growth"),
            ("gross_margin", "Gross Margin"),
            ("operating_margin", "Operating Margin"),
            ("net_margin", "Net Margin"),
        ]:
            v = d.get(key) or deep.get(key)
            if v is not None:
                rows.append((label, _fmt(v * 100 if abs(float(v)) < 1 else v, suffix="%")))

        if not rows:
            return []

        return [
            Paragraph("Financial Performance", s["SectionHeader"]),
            HRFlowable(width="100%", thickness=0.5, color=_BORDER),
            Spacer(1, 6),
            _two_col_table(rows),
            Spacer(1, 8),
        ]

    def _valuation(self, d: Dict) -> List:
        s = self.styles
        ticker       = d.get("ticker", "")
        currency_sym = _PDF_RUPEE_SYMBOL if (str(ticker).endswith(".NS") or str(ticker).endswith(".BO")) else "$"
        # Use the shared helper — handles empty sector, primary_model flag, and known ticker list
        is_fin = _is_financial_sector(d)

        # ── Resolve nested valuation structure ────────────────────────────
        # The graph stores valuation in two different shapes depending on path:
        #   Fast path:  report_data["valuation"]["details"]["models"]["excess_returns"]
        #   Scoring path: comprehensive_score.valuation.key_metrics.intrinsic_value
        val_wrapper  = d.get("valuation") or d.get("dcf_valuation") or d.get("dcf") or {}
        val_details  = val_wrapper.get("details") or val_wrapper
        models       = val_details.get("models") or {}
        consolidated = val_details.get("consolidated_valuation") or {}
        inputs       = val_details.get("inputs") or {}
        cf_data      = d.get("comprehensive_fundamentals") or {}

        # Scoring path: comprehensive_score pillar key_metrics
        # The report builder may embed these at top level or under comprehensive_score
        cs = d.get("comprehensive_score") or d.get("scoring") or {}
        valuation_pillar_metrics = (cs.get("valuation") or {}).get("key_metrics") or {}

        rows = []

        # ── Current price ─────────────────────────────────────────────────
        price = d.get("_price") or _f_safe(inputs.get("current_price"))
        if price:
            rows.append(("Current Price", f"{currency_sym}{_fmt(price)}"))

        if is_fin:
            # ══ Financial Services path ═══════════════════════════════════
            #
            # Priority order for Excess Returns intrinsic value:
            #   1. valuation.details.models.excess_returns  (valuation.py output)
            #   2. comprehensive_score.valuation.key_metrics.intrinsic_value  (scoring path, post-fix)
            #   3. comprehensive_fundamentals.intrinsic_value
            #   4. Recompute inline from BVPS + ROE if neither above is available

            er = models.get("excess_returns") or {}
            er_inputs = er.get("inputs") or {}

            # Resolve ROE and BVPS from every possible source for inline recompute
            roe_raw = (
                _f_safe(er_inputs.get("ROE"))
                or _f_safe(inputs.get("return_on_equity"))
                or _f_safe(valuation_pillar_metrics.get("roe"))
                or _f_safe(cf_data.get("returnOnEquity"))
            )
            bvps_raw = (
                _f_safe(er_inputs.get("BVPS"))
                or _f_safe(inputs.get("book_value_ps"))
                or _f_safe(valuation_pillar_metrics.get("bvps"))
                or _f_safe(cf_data.get("bookValue"))
            )
            ke_raw = (
                _f_safe(er_inputs.get("cost_of_equity"))
                or _f_safe(inputs.get("cost_of_equity"))
                or _f_safe(valuation_pillar_metrics.get("cost_of_equity"))
            )

            iv = _f_safe(er.get("intrinsic_value"))

            # Fallback 2: from scoring pillar metrics
            if not iv or iv <= 0:
                iv_from_scoring = _f_safe(valuation_pillar_metrics.get("intrinsic_value"))
                if iv_from_scoring and iv_from_scoring > 0:
                    iv = iv_from_scoring

            # Fallback 3: from comprehensive_fundamentals
            if not iv or iv <= 0:
                iv = _f_safe(cf_data.get("intrinsic_value"))

            # Fallback 4: inline recompute from BVPS + ROE (display-only, clearly labelled)
            _iv_recomputed = False
            if (not iv or iv <= 0) and roe_raw and bvps_raw and bvps_raw > 0:
                ke_used = ke_raw or (0.07 + 1.0 * 0.065)  # default Ke for Indian bank
                tg_used = 0.025
                if ke_used > tg_used:
                    excess = roe_raw - ke_used
                    iv = round(bvps_raw + (bvps_raw * excess) / (ke_used - tg_used), 2)
                    _iv_recomputed = True

            mos = (
                _f_safe(er.get("upside_pct"))            # percentage form from valuation.py
                or _f_safe(valuation_pillar_metrics.get("margin_of_safety"))
            )

            if iv and iv > 0:
                label = "Intrinsic Value (Excess Returns) ⚠ est." if _iv_recomputed else "Intrinsic Value (Excess Returns)"
                rows.append((label, f"{currency_sym}{_fmt(iv)}"))
                if price and price > 0:
                    implied_upside = (iv - price) / price * 100
                    rows.append(("Implied Upside (vs IV)", f"{implied_upside:+.1f}%"))

            # ROE / BVPS / Ke display (use already-resolved variables)
            if roe_raw is not None:
                roe_display = roe_raw * 100 if roe_raw < 1 else roe_raw
                rows.append(("Return on Equity", f"{_fmt(roe_display)}%"))
            if bvps_raw is not None:
                rows.append(("Book Value / Share", f"{currency_sym}{_fmt(bvps_raw)}"))
            if ke_raw is not None:
                rows.append(("Cost of Equity (Ke)", f"{_fmt(ke_raw * 100 if ke_raw < 1 else ke_raw)}%"))

            # Margin of safety or upside
            if mos is not None:
                if abs(mos) > 1:  # already in percentage form
                    rows.append(("Excess Returns Upside", f"{mos:+.1f}%"))
                else:
                    rows.append(("Excess Returns Upside", f"{mos * 100:+.1f}%"))

            # P/B peer comparables
            comps = models.get("comparables") or {}
            if comps.get("applicable"):
                pb_comp = (comps.get("multiples_analysis") or {}).get("pb_based") or {}
                pe_comp = (comps.get("multiples_analysis") or {}).get("pe_based") or {}
                if pb_comp.get("current_pb") is not None or pb_comp.get("current_multiple") is not None:
                    cur_pb = pb_comp.get("current_pb") or pb_comp.get("current_multiple")
                    rows.append(("Current P/B",       f"{_fmt(cur_pb)}x"))
                if pb_comp.get("peer_avg_pb") or pb_comp.get("peer_average"):
                    peer_pb = pb_comp.get("peer_avg_pb") or pb_comp.get("peer_average")
                    rows.append(("Peer Avg P/B",       f"{_fmt(peer_pb)}x"))
                pb_iv = pb_comp.get("implied_price")
                if pb_iv:
                    rows.append(("P/B Implied Price",  f"{currency_sym}{_fmt(pb_iv)}"))
                pe_iv = pe_comp.get("implied_price")
                if pe_iv:
                    rows.append(("P/E Implied Price",  f"{currency_sym}{_fmt(pe_iv)}"))
                if comps.get("peer_group"):
                    rows.append(("Peer Group",          str(comps["peer_group"])[:70]))

            # Suppress the misleading DCF row if we have actual valuation data
            if not iv and not comps.get("applicable"):
                rows.append(("DCF Model", "Not applicable — Financial Services. Using Excess Returns (Residual Income) model."))

            # DDM if applicable for bank (some pay dividends)
            ddm = models.get("ddm") or {}
            if ddm.get("applicable"):
                ddm_v = _f_safe(ddm.get("ddm_value_per_share"))
                if ddm_v:
                    rows.append(("DDM Value / Share", f"{currency_sym}{_fmt(ddm_v)}"))

        else:
            # ══ Non-financial path ════════════════════════════════════════
            # Show DCF intrinsic value (base case) — this is what the UI "DCF Valuation" card shows.
            # Consolidated Target is shown separately ONLY when it's above the current price.
            # If it's below current price it would contradict a BUY recommendation and confuse
            # investors — instead we show a note explaining the growth-premium situation.
            dcf = models.get("dcf") or {}
            dcf_base_p = None
            if dcf.get("applicable"):
                dcf_base_p = _f_safe((dcf.get("base_case") or {}).get("intrinsic_price", {}).get("base"))
                if dcf_base_p:
                    rows.append(("Intrinsic Value (DCF)", f"{currency_sym}{_fmt(dcf_base_p)}"))
                if dcf.get("scenarios"):
                    scens = dcf["scenarios"]
                    for label, key in [("Conservative", "conservative"), ("Optimistic", "optimistic")]:
                        sp = _f_safe((scens.get(key) or {}).get("intrinsic_price", {}).get("base"))
                        if sp:
                            rows.append((f"DCF {label}", f"{currency_sym}{_fmt(sp)}"))
            elif dcf.get("reason"):
                rows.append(("DCF Model", str(dcf["reason"])[:90]))

            # Consolidated target: weighted average of models.
            # Only shown when it's above current price (otherwise it contradicts Buy thesis).
            # When excluded, show a brief note so the report remains transparent.
            cons_iv = _f_safe(consolidated.get("target_price"))
            price_check = d.get("_price")
            if cons_iv and cons_iv != dcf_base_p:
                if price_check and price_check > 0 and cons_iv < price_check:
                    # Consolidated is below current price — stock is trading at a growth premium.
                    # Showing this as a target would contradict the Buy recommendation.
                    rows.append(("Consolidated Target", (
                        f"Not shown — stock trades at growth premium "
                        f"(DCF: {currency_sym}{_fmt(dcf_base_p, decimals=0)} vs "
                        f"peer multiples which imply lower values). "
                        f"Primary valuation anchor is DCF Intrinsic Value."
                    )))
                else:
                    rows.append(("Consolidated Target", f"{currency_sym}{_fmt(cons_iv)}"))

            # DDM
            ddm = models.get("ddm") or {}
            if ddm.get("applicable"):
                ddm_v = _f_safe(ddm.get("ddm_value_per_share"))
                if ddm_v:
                    rows.append(("DDM Value / Share", f"{currency_sym}{_fmt(ddm_v)}"))

        # ── Consolidated target + return (both paths) ─────────────────────
        cons_target    = _f_safe(consolidated.get("target_price")) or _f_safe(cf_data.get("target_price"))
        analyst_target = d.get("_analyst_target")
        price_for_check = d.get("_price")

        # Stale analyst target guard: for Indian stocks, if the analyst target is >40%
        # below the current price it almost certainly reflects pre-merger / unadjusted data
        # from yfinance (e.g. HDFCBANK.NS post-HDFC-merger).  Display a warning instead of
        # using it as the authoritative target.
        _analyst_target_stale = False
        if analyst_target and price_for_check and price_for_check > 0:
            is_indian_ticker = str(ticker).upper().endswith(".NS") or str(ticker).upper().endswith(".BO")
            if is_indian_ticker and (analyst_target - price_for_check) / price_for_check < -0.40:
                _analyst_target_stale = True

        if _analyst_target_stale:
            rows.append(("Price Target (12M)", f"⚠ DATA QUALITY — analyst target "
                         f"{currency_sym}{_fmt(analyst_target, decimals=0)} appears stale "
                         f"(>40% below current price {currency_sym}{_fmt(price_for_check, decimals=0)}). "
                         f"Verify against live NSE/BSE data."))
            display_target = cons_target  # fall back to model-derived target if available
        else:
            display_target = analyst_target or cons_target

        if display_target and not _analyst_target_stale:
            rows.append(("Price Target (12M)", f"{currency_sym}{_fmt(display_target, decimals=0)}"))

        return_pct = _f_safe((d.get("decision") or {}).get("expected_return_pct"))
        if return_pct is not None:
            # If analyst target is stale, recompute return from model target vs current price
            if _analyst_target_stale and display_target and price_for_check and price_for_check > 0:
                return_pct = (display_target - price_for_check) / price_for_check * 100
            rows.append(("Expected Return", f"{return_pct:+.1f}%"))

        # Ke / terminal growth
        if inputs.get("cost_of_equity"):
            ke = inputs["cost_of_equity"]
            rows.append(("Cost of Equity (Ke)", f"{_fmt(ke * 100 if ke < 1 else ke)}%"))
        if inputs.get("discount_rate"):
            dr = inputs["discount_rate"]
            rows.append(("Discount Rate", f"{_fmt(dr * 100 if dr < 1 else dr)}%"))
        if inputs.get("terminal_growth"):
            tg = inputs["terminal_growth"]
            rows.append(("Terminal Growth Rate", f"{_fmt(tg * 100 if tg < 1 else tg)}%"))

        # Data integrity flags
        integrity = consolidated.get("data_integrity") or {}
        if integrity.get("status") == "LOW_CONFIDENCE":
            for flag in (integrity.get("flags") or []):
                rows.append(("⚠ Data Integrity", str(flag)[:90]))

        if not rows:
            return []

        return [
            Paragraph("Valuation", s["SectionHeader"]),
            HRFlowable(width="100%", thickness=0.5, color=_BORDER),
            Spacer(1, 6),
            _two_col_table(rows),
            Spacer(1, 8),
        ]

    def _technical(self, d: Dict) -> List:
        s = self.styles
        tech = d.get("technical_analysis") or d.get("technicals") or d.get("tech_data") or {}
        ticker       = d.get("ticker", "")
        currency_sym = _PDF_RUPEE_SYMBOL if (str(ticker).endswith(".NS") or str(ticker).endswith(".BO")) else "$"
        price        = d.get("_price")

        rows = []
        for key, label in [
            ("trend",            "Trend"),
            ("signal",           "Signal"),
            ("rsi",              "RSI"),
            ("macd",             "MACD"),
            ("support",          "Support"),
            ("resistance",       "Resistance"),
            ("moving_avg_50",    "50-Day MA"),
            ("moving_avg_200",   "200-Day MA"),
            ("momentum_score",   "Momentum Score"),
            ("volatility",       "Volatility"),
        ]:
            v = tech.get(key) or d.get(key)
            if v is not None:
                rows.append((label, str(v) if isinstance(v, str) else _fmt(v)))

        # Entry zone — use sanitized values from comprehensive_fundamentals
        # (already validated low < high and within ±50% of price by _sanitize_report)
        cf     = d.get("comprehensive_fundamentals") or {}
        ez_low  = _f_safe(cf.get("entry_zone_low"))
        ez_high = _f_safe(cf.get("entry_zone_high"))
        if ez_low is not None and ez_high is not None:
            rows.append(("Entry Zone", f"{currency_sym}{_fmt(ez_low)} – {currency_sym}{_fmt(ez_high)}"))
            # When the current price is below the entry zone, the stock is trading at a
            # more attractive level than the model calculated. Label this clearly as a
            # "Value Buy Zone" — the price has come to the investor rather than the investor
            # having to wait for it to pull back.
            if price and price > 0 and price < ez_low:
                gap_pct = (ez_low - price) / ez_low * 100
                rows.append((
                    "✓ In Value Buy Zone",
                    f"Price ({currency_sym}{_fmt(price)}) is {gap_pct:.1f}% below entry zone low "
                    f"({currency_sym}{_fmt(ez_low)}). Stock has entered the value buy range — "
                    f"favourable entry for investors aligned with the Buy thesis."
                ))
        elif tech.get("entry_zone") or d.get("entry_zone"):
            # Raw string fallback — only render if it looks sane
            raw_ez = str(tech.get("entry_zone") or d.get("entry_zone"))
            rows.append(("Entry Zone", raw_ez))

        # Stop-loss
        stop_loss = _f_safe(cf.get("stop_loss")) or _f_safe(d.get("stop_loss"))
        if stop_loss is not None:
            rows.append(("Stop Loss", f"{currency_sym}{_fmt(stop_loss)}"))

        if not rows:
            return []

        return [
            Paragraph("Technical Analysis", s["SectionHeader"]),
            HRFlowable(width="100%", thickness=0.5, color=_BORDER),
            Spacer(1, 6),
            _two_col_table(rows),
            Spacer(1, 8),
        ]

    def _risk_factors(self, d: Dict) -> List:
        s = self.styles
        risks = (
            d.get("risk_factors") or
            d.get("risks") or
            (d.get("decision", {}) or {}).get("bear_points") or
            []
        )

        if not risks:
            return []

        elems = [
            Paragraph("Risk Factors", s["SectionHeader"]),
            HRFlowable(width="100%", thickness=0.5, color=_BORDER),
            Spacer(1, 6),
            _bullet_list([str(r) for r in risks], s["BodyText"]),
            Spacer(1, 8),
        ]
        return elems

    def _analyst_sentiment(self, d: Dict) -> List:
        s = self.styles

        # Both fields use {summary, confidence, details} wrapper — unwrap first
        def _unwrap(raw: Any) -> Dict:
            """If the value is a wrapper dict with a 'details' key, return details.
            Otherwise return the dict as-is (legacy flat format)."""
            if not isinstance(raw, dict):
                return {}
            if "details" in raw and isinstance(raw["details"], dict):
                return raw["details"]
            return raw

        analyst_raw   = d.get("analyst_recommendations") or d.get("analyst_data") or {}
        sentiment_raw = d.get("news_sentiment") or d.get("sentiment") or {}
        analyst   = _unwrap(analyst_raw)
        sentiment = _unwrap(sentiment_raw)

        # analyst wrapper-level fields (confidence lives at wrapper level)
        analyst_confidence = _f_safe(analyst_raw.get("confidence")) if isinstance(analyst_raw, dict) else None

        rows = []

        # ── Analyst data ──────────────────────────────────────────────────
        # consensus: nested under recommendation_summary
        rec_summary = analyst.get("recommendation_summary") or {}
        consensus = (
            rec_summary.get("consensus")
            or analyst.get("consensus")
            or analyst.get("recommendation")
        )
        if consensus:
            rows.append(("Analyst Consensus", str(consensus).replace("_", " ").title()))

        n_analysts = (
            _f_safe(rec_summary.get("analyst_count"))
            or _f_safe(analyst.get("num_analysts"))
            or _f_safe(analyst.get("numberOfAnalysts"))
        )
        if n_analysts:
            rows.append(("Number of Analysts", str(int(n_analysts))))

        # Price targets
        targets = analyst.get("target_prices") or {}
        mean_t  = _f_safe(targets.get("mean"))
        high_t  = _f_safe(targets.get("high"))
        low_t   = _f_safe(targets.get("low"))
        ticker  = d.get("ticker", "")
        csym    = _PDF_RUPEE_SYMBOL if (str(ticker).endswith(".NS") or str(ticker).endswith(".BO")) else "$"
        if mean_t:
            rows.append(("Mean Price Target",  f"{csym}{_fmt(mean_t, decimals=0)}"))
        if high_t:
            rows.append(("High Target",        f"{csym}{_fmt(high_t, decimals=0)}"))
        if low_t:
            rows.append(("Low Target",         f"{csym}{_fmt(low_t,  decimals=0)}"))

        # Implied return from analyst data
        implied_ret = _f_safe(analyst.get("implied_return_pct") or analyst.get("implied_return"))
        if implied_ret:
            rows.append(("Implied Return",     f"{implied_ret:+.1f}%"))

        # Analyst confidence (wrapper level)
        if analyst_confidence is not None:
            rows.append(("Analyst Data Confidence",
                         _fmt(analyst_confidence * 100 if analyst_confidence <= 1 else analyst_confidence, suffix="%")))

        # Buy/Hold/Sell breakdown
        recent = analyst.get("recent_recommendations") or {}
        buy_pct  = _f_safe(analyst.get("buy_percentage")  or analyst.get("buy_pct"))
        hold_pct = _f_safe(analyst.get("hold_percentage") or analyst.get("hold_pct"))
        sell_pct = _f_safe(analyst.get("sell_percentage") or analyst.get("sell_pct"))
        if buy_pct is not None:
            rows.append(("Buy %",  f"{_fmt(buy_pct)}%"))
        if hold_pct is not None:
            rows.append(("Hold %", f"{_fmt(hold_pct)}%"))
        if sell_pct is not None:
            rows.append(("Sell %", f"{_fmt(sell_pct)}%"))

        # ── Sentiment data ────────────────────────────────────────────────
        # sentiment_raw wrapper has its own confidence + details
        sent_conf = _f_safe(sentiment_raw.get("confidence")) if isinstance(sentiment_raw, dict) else None

        for key, label in [
            ("combined_sentiment",   "Combined Sentiment Score"),
            ("news_sentiment_score", "News Sentiment Score"),
            ("valuepickr_score",     "ValuePickr Score"),
            ("news_sentiment",       "News Sentiment"),
        ]:
            v = _f_safe(sentiment.get(key)) or _f_safe(d.get(key))
            if v is not None:
                rows.append((label, _fmt(v)))

        # Sentiment label if available
        for key, label in [
            ("price_sentiment",    "Price Sentiment"),
            ("news_label",         "News Sentiment Label"),
            ("overall_sentiment",  "Overall Sentiment"),
        ]:
            v = sentiment.get(key) or d.get(key)
            if isinstance(v, str) and v:
                rows.append((label, v))

        if not rows:
            return []

        return [
            Paragraph("Analyst & Sentiment", s["SectionHeader"]),
            HRFlowable(width="100%", thickness=0.5, color=_BORDER),
            Spacer(1, 6),
            _two_col_table(rows),
            Spacer(1, 8),
        ]

    def _appendix(self, d: Dict) -> List:
        s = self.styles
        ticker = d.get("ticker", "")

        elems = [
            PageBreak(),
            Paragraph("Appendix", s["SectionHeader"]),
            HRFlowable(width="100%", thickness=0.5, color=_BORDER),
            Spacer(1, 8),
            Paragraph("Methodology", s["SubsectionHeader"]),
            Paragraph(
                "This report was generated using EquiSense AI's proprietary analysis engine, which combines "
                "fundamental analysis (financial ratios, DCF valuation, peer comparisons), technical analysis "
                "(multiple indicators and chart patterns), sentiment analysis (news and community sources), "
                "and sector rotation signals.",
                s["BodyText"],
            ),
            Spacer(1, 6),
            Paragraph("Data Sources", s["SubsectionHeader"]),
            _bullet_list([
                "Yahoo Finance — price, volume and fundamental data",
                "BSE / NSE — Indian market filings and shareholding data",
                "SEC Edgar — regulatory filings for US stocks",
                "ValuePickr — Indian investor community sentiment",
                "News APIs — real-time news sentiment analysis",
            ], s["BodyText"]),
            Spacer(1, 6),
            HRFlowable(width="100%", thickness=0.5, color=_BORDER),
            Spacer(1, 4),
            Paragraph(
                f"Report generated by EquiSense AI on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}  |  "
                f"Ticker: {ticker}  |  research@equisense.ai",
                s["Disclaimer"],
            ),
            Paragraph(
                "This report is for informational purposes only. It does not constitute financial advice. "
                "Always consult a qualified financial advisor before making investment decisions.",
                s["Disclaimer"],
            ),
        ]
        return elems


# ─── ReportBuilder (unchanged public API) ──────────────────────────────────

class ReportBuilder:
    """Fluent builder for custom reports (backwards-compatible)."""

    def __init__(self):
        self.generator = PDFReportGenerator()
        self.metadata  = None
        self.sections: List[ReportSection] = []

    def set_metadata(self, ticker: str, company_name: str, **kwargs) -> "ReportBuilder":
        self.metadata = ReportMetadata(
            ticker=ticker,
            company_name=company_name,
            report_date=datetime.now(),
            **kwargs,
        )
        return self

    def add_section(self, title: str, content: str,
                    data: Dict[str, Any] = None,
                    chart_data: Dict[str, Any] = None,
                    include_chart: bool = False) -> "ReportBuilder":
        self.sections.append(ReportSection(
            title=title, content=content,
            data=data, chart_data=chart_data, include_chart=include_chart,
        ))
        return self

    async def build(self, include_charts: bool = True) -> bytes:
        if not self.metadata:
            raise ValueError("Report metadata not set")
        # Build a minimal report_data dict from metadata + sections
        report_data = {
            "ticker":       self.metadata.ticker,
            "company_name": self.metadata.company_name,
        }
        buf = self.generator.generate_report(report_data)
        return buf.getvalue()

    @staticmethod
    def get_base64_pdf(pdf_bytes: bytes) -> str:
        return base64.b64encode(pdf_bytes).decode("utf-8")


# ─── Global singleton ───────────────────────────────────────────────────────

_report_generator: Optional[PDFReportGenerator] = None


def get_report_generator() -> PDFReportGenerator:
    global _report_generator
    if _report_generator is None:
        _report_generator = PDFReportGenerator()
    return _report_generator


# ─── THE MISSING FUNCTION main.py imports ──────────────────────────────────

def generate_pdf_report(report_data: Dict[str, Any]) -> io.BytesIO:
    """
    Top-level function imported by main.py.

    Accepts the raw report_data dict from the analysis graph and returns
    an io.BytesIO ready to be passed directly to FastAPI's StreamingResponse.
    """
    return get_report_generator().generate_report(report_data)
