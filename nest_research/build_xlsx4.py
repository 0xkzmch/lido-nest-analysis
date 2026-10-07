import csv
from datetime import date, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment

F = "Arial"
f_norm = Font(name=F, size=10)
f_bold = Font(name=F, size=10, bold=True)
f_title = Font(name=F, size=13, bold=True)
f_in = Font(name=F, size=10, color="0000FF")
f_link = Font(name=F, size=10, color="008000")
f_note = Font(name=F, size=9, italic=True, color="666666")
fill_in = PatternFill("solid", fgColor="FFFF00")
fill_hdr = PatternFill("solid", fgColor="DDEBF7")
thin = Side(style="thin", color="BFBFBF")
USD = '$#,##0;($#,##0);-'
USD2 = '$#,##0.00;($#,##0.00);-'
PCT = '0.00%;(0.00%);-'
DT = 'yyyy-mm-dd'

wb = Workbook()

def hdr(ws, row, labels, col=1):
    for i, l in enumerate(labels):
        c = ws.cell(row=row, column=col + i, value=l)
        c.font = f_bold; c.fill = fill_hdr
        c.alignment = Alignment(wrap_text=True, vertical="center")

def inp(c, v, fmt=None, key=False):
    c.value = v; c.font = f_in
    if key: c.fill = fill_in
    if fmt: c.number_format = fmt

def widths(ws, ws_w):
    for col, w in ws_w.items(): ws.column_dimensions[col].width = w

# ---------------- Guide ----------------
g = wb.active; g.title = "Guide"
lines = [
 ("NEST buyback model (Lido DAO), v1, 28.09.2026", f_title),
 ("", f_norm),
 ("How to use", f_bold),
 ("1. Variants sheet: each row is a separate variant of the buyback rule. Parameters are in yellow cells, results are computed in the same row and stay next to them, so all variants can be compared at once.", f_norm),
 ("2. To test a new idea, fill in the ‘Custom variant’ row or change any row. In the ‘Conclusion’ column, record what the variant showed.", f_norm),
 ("3. The daily calculation for each variant is on the Engine sheet, with a separate block of columns per variant. There you can see what each figure is made of.", f_norm),
 ("4. Future scenarios via four levers (TVL, yield, DAO share, ETH price) are on the Forward sheet.", f_norm),
 ("5. Dynamic scale: in the ‘Scale’ column choose ‘progressive’, then the surplus above the threshold is split into three tiers with their own shares.", f_norm),
 ("6. Debt policy (‘Deficit’ column): accumulates, floor N days, does not accumulate, decay, reset by period, rolling window. Explanations below the table on the Variants sheet.", f_norm),
 ("7. Metrics for comparing models (AG–AK): LDO bought, DAO economic surplus for the period, profit coverage, overspend in loss-making periods, number of buyback activations. A good model has overspend near zero and coverage no more than 100%, while buybacks and LDO are as large as possible.", f_norm),
 ("", f_norm),
 ("Sheets", f_bold),
 ("Variants: model variants and their results.", f_norm),
 ("Engine: daily calculation of the NEST budget for each variant using contract formulas (threshold, share, caps, minimum purchase, deficit policy).", f_norm),
 ("Data: 1,002 actual fee inflows to the DAO treasury since 01.01.2024, one per daily rebase. Transaction hash, stETH, Chainlink prices (roundId). USD is computed by formula.", f_norm),
 ("Expenses: Foundations expenses by period from Lido reports and cost of revenue (referral payouts and other).", f_norm),
 ("NEST_check: reproduction of the NEST onchain budget at all checkpoints. Error should be 0.", f_norm),
 ("Recon: true-up of onchain inflows against Lido reports.", f_norm),
 ("Forward: scenarios 12 months ahead.", f_norm),
 ("Grid_Python: scenario grid from the Python model, for true-up (values, not formulas).", f_norm),
 ("Lists: helper lists for dropdown menus.", f_norm),
 ("", f_norm),
 ("Colors", f_bold),
 ("Blue text on yellow background: inputs you can change. Blue text without background: source data (onchain or from reports). Black: formulas.", f_norm),
 ("", f_norm),
 ("What the revenue series is", f_bold),
 ("Actual staking fee inflows to the treasury (after the node operator share, before referral payouts), valued at Chainlink stETH/ETH × ETH/USD at the inflow block. This is the same oracle route as NEST uses, but not its historical counter: NEST converts to USD later, in a separate call. The stETH amount matches NEST exactly, USD differs by −0.044%.", f_norm),
 ("Methodology details and all checks are in base/README.md.", f_norm),
 ("", f_norm),
 ("Assumptions", f_bold),
 ("Expenses for 2024, 2025 and H2 2026 by line item (staking, shared services) are unknown; for threshold variants 2 and 3 they are split using H1 2026 proportions. H2 2026 expenses = annual forecast $37.7M minus H1 actuals.", f_norm),
 ("The annual cap is computed in 365-day windows from the simulation start date, as the contract does from the activation date.", f_norm),
]
for i, (t, f) in enumerate(lines, 1):
    c = g.cell(row=i, column=1, value=t); c.font = f; c.alignment = Alignment(wrap_text=True, vertical="top")
g.column_dimensions["A"].width = 130

# ---------------- Data ----------------
d = wb.create_sheet("Data")
rows = list(csv.DictReader(open("base/treasury_fee_inflows.csv")))
hdr(d, 1, ["Date (UTC)", "stETH to treasury", "stETH/ETH (Chainlink)", "ETH/USD (Chainlink)", "USD value", "Source",
           "Block", "Tx hash", "stETH/ETH roundId", "ETH/USD roundId", "Price flag"])
for i, r in enumerate(rows, 2):
    d.cell(row=i, column=1, value=date.fromisoformat(r["date"])).number_format = DT
    inp(d.cell(row=i, column=2), float(r["steth"]), "#,##0.000000")
    inp(d.cell(row=i, column=3), float(r["steth_eth"]), "0.000000")
    inp(d.cell(row=i, column=4), float(r["eth_usd"]), "#,##0.00")
    d.cell(row=i, column=5, value=f"=B{i}*C{i}*D{i}").number_format = USD2
    d.cell(row=i, column=6, value=r["source"])
    d.cell(row=i, column=7, value=int(r["block"]))
    d.cell(row=i, column=8, value=r["tx_hash"])
    d.cell(row=i, column=9, value=r["steth_eth_roundId"])
    d.cell(row=i, column=10, value=r["eth_usd_roundId"])
    d.cell(row=i, column=11, value=r["price_flag"])
    for col in (1, 5, 6, 7, 8, 9, 10, 11): d.cell(row=i, column=col).font = f_norm
N = len(rows); LAST = N + 1
d.freeze_panes = "A2"
widths(d, {"A": 12, "B": 16, "C": 14, "D": 14, "E": 14, "F": 24, "G": 11, "H": 68, "I": 22, "J": 22, "K": 26})
d.cell(row=1, column=2).comment = Comment("Actual stETH transfer to the treasury agent 0x3e40...9C8c: until 24.12.2025 minted at rebase, afterwards transferred from distributor 0x23ed...cddf. Source: base/treasury_fee_inflows.csv", "model")
d.cell(row=1, column=3).comment = Comment("Chainlink stETH/ETH proxy 0x86392dC19c0b719886221c78AB11eb8Cf5c52812, latestRoundData() at the inflow block", "model")
d.cell(row=1, column=4).comment = Comment("Chainlink ETH/USD proxy 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419, latestRoundData() at the inflow block", "model")

DA = f"Data!$A$2:$A${LAST}"; DB = f"Data!$B$2:$B${LAST}"; DD = f"Data!$D$2:$D${LAST}"; DE = f"Data!$E$2:$E${LAST}"

# ---------------- Expenses ----------------
e = wb.create_sheet("Expenses")
e["A1"] = "Foundations expenses and cost of revenue by period"; e["A1"].font = f_title
hdr(e, 4, ["Period", "Start", "End", "Days", "Foundations expenses, $", "Staking (core+growth), $", "Shared services, $",
           "Onchain inflows, $", "Cost of revenue, $", "Cost share", "Daily threshold: all expenses",
           "Daily threshold: staking+shared", "Daily threshold: staking", "Report: net staking revenue, $", "Source / assumption"])
per = [
 ("2024", date(2024,1,1), date(2024,12,31)),
 ("2025", date(2025,1,1), date(2025,12,31)),
 ("Q1 2026", date(2026,1,1), date(2026,3,31)),
 ("Q2 2026", date(2026,4,1), date(2026,6,30)),
 ("H2 2026", date(2026,7,1), date(2026,12,31)),
]
for i, (lab, s, en) in enumerate(per, 5):
    e.cell(row=i, column=1, value=lab).font = f_norm
    e.cell(row=i, column=2, value=s).number_format = DT
    e.cell(row=i, column=3, value=en).number_format = DT
    e.cell(row=i, column=4, value=f"=C{i}-B{i}+1")
    e.cell(row=i, column=8, value=f'=SUMIFS({DE},{DA},">="&B{i},{DA},"<="&C{i})').number_format = USD
    e.cell(row=i, column=10, value=f"=IF(H{i}>0,I{i}/H{i},0)").number_format = PCT
    e.cell(row=i, column=11, value=f"=E{i}/D{i}*1").number_format = USD
    e.cell(row=i, column=12, value=f"=(F{i}+G{i})/D{i}").number_format = USD
    e.cell(row=i, column=13, value=f"=F{i}/D{i}").number_format = USD
# expenses totals
inp(e["E5"], 52100000, USD); inp(e["E6"], 45500000, USD); inp(e["E7"], 6920000, USD); inp(e["E8"], 7410000, USD)
e["E9"] = "=Expenses!$B$13-E7-E8"; e["E9"].number_format = USD
inp(e["F7"], 4380000, USD); inp(e["F8"], 4600000, USD); inp(e["G7"], 1570000, USD); inp(e["G8"], 1580000, USD)
for r in (5, 6, 9):
    e[f"F{r}"] = f"=E{r}*$B$14"; e[f"G{r}"] = f"=E{r}*$B$15"
    e[f"F{r}"].number_format = USD; e[f"G{r}"].number_format = USD
# cost of revenue
inp(e["I5"], 3100000, USD); inp(e["I6"], 4100000, USD)
inp(e["N7"], 8630000, USD); inp(e["N8"], 7080000, USD)
e["I7"] = "=H7-N7"; e["I8"] = "=H8-N8"; e["I9"] = "=H9*$B$16"
for c in ("I7", "I8", "I9"): e[c].number_format = USD
e["O5"] = "Expenses and referral payouts: GOOSE-2025 & EGGs-2025 Final Report (research.lido.fi/t/11304)"
e["O6"] = "Same"
e["O7"] = "H1 2026 Report, P&L (lido.fi/ldo-hub/reports/h1-2026); costs = onchain − net revenue"
e["O8"] = "Same"
e["O9"] = "Expenses = annual forecast (B13) − H1 actuals; line items and cost share by H1 proportions (assumption)"
for r in range(5, 10): e[f"O{r}"].font = f_note
e["A12"] = "Inputs and derived values"; e["A12"].font = f_bold
e["A13"] = "Expense forecast for 2026, $"; inp(e["B13"], 37700000, USD, key=True)
e["C13"] = "H1 2026 Report: full-year spending projected at ~$37.7M"; e["C13"].font = f_note
e["A14"] = "Staking share of expenses (H1 2026)"; e["B14"] = "=(F7+F8)/(E7+E8)"; e["B14"].number_format = PCT
e["A15"] = "Shared services share of expenses (H1 2026)"; e["B15"] = "=(G7+G8)/(E7+E8)"; e["B15"].number_format = PCT
e["A16"] = "Cost of revenue share (H1 2026)"; e["B16"] = "=(I7+I8)/(H7+H8)"; e["B16"].number_format = PCT
e["A17"] = "Onchain H2 2026 is incomplete (data up to the date of the last Data row); the H2 cost share is taken from H1."; e["A17"].font = f_note
widths(e, {"A": 40, "B": 14, "C": 12, "D": 7, "E": 17, "F": 17, "G": 15, "H": 17, "I": 17, "J": 10, "K": 14, "L": 14, "M": 14, "N": 17, "O": 80})

from openpyxl.utils import get_column_letter as CL
import json as _json

# ---- extra data: LDO price in Data!L, economic surplus per period in Expenses!P ----
ldo = _json.load(open("data/ldo_px.json"))
d.cell(row=1, column=12, value="LDO/USD (DefiLlama, ffill ≤1 day)").font = f_bold
d.cell(row=1, column=12).fill = fill_hdr
for i, pxv in enumerate(ldo, 2):
    inp(d.cell(row=i, column=12), float(pxv), "0.0000")
d.column_dimensions["L"].width = 16
e["P4"] = "Economic surplus for the period (based on available data), $"; e["P4"].font = f_bold; e["P4"].fill = fill_hdr
e["P4"].alignment = Alignment(wrap_text=True, vertical="center")
for r in range(5, 10):
    e[f"P{r}"] = f'=H{r}-I{r}-K{r}*COUNTIFS({DA},">="&B{r},{DA},"<="&C{r})'; e[f"P{r}"].number_format = USD
e.column_dimensions["P"].width = 20
e["A18"] = "Economic surplus = net staking revenue − all Foundations expenses for the days with available data."; e["A18"].font = f_note

# ---------------- Lists ----------------
ls = wb.create_sheet("Lists")
opts = {"A": ["fixed", "expenses"], "B": ["all", "staking+shared", "staking"], "C": ["as NEST", "net"],
        "D": ["accumulates", "floor N days", "does not accumulate", "decay", "reset by period", "rolling window"], "E": ["no", "progressive"], "F": ["quarter", "year"]}
heads = {"A": "Threshold type", "B": "Expenses for threshold", "C": "Revenue base", "D": "Deficit policy", "E": "Scale", "F": "Reset period"}
for col, vals in opts.items():
    ls[f"{col}1"] = heads[col]; ls[f"{col}1"].font = f_bold
    for i, val in enumerate(vals, 2): ls[f"{col}{i}"] = val
ls["H1"] = "Helper sheet with lists for dropdown menus"; ls["H1"].font = f_note

# ---------------- Variants ----------------
v = wb.create_sheet("Variants", 1)
v["A1"] = "Buyback model variants: one row = one variant, results are computed in the same row"; v["A1"].font = f_title
v["A2"] = ("Change the yellow cells (B–X). Results (Y–AK) recalculate automatically. Record your conclusion in column AL. "
           "Daily calculation for each variant on the Engine sheet."); v["A2"].font = f_note
cols = ["№", "Variant name", "Start", "End", "Threshold type", "Fixed threshold, $/year", "Expenses for threshold",
        "Expense multiplier", "Revenue base", "Share (or tier 1 share)", "Daily cap, $", "Annual cap, $", "Min. purchase, $",
        "Deficit", "N days (floor / window)", "Initial budget, $",
        "Scale", "Bound 1, $/year above threshold", "Bound 2, $/year above threshold", "Tier 2 share", "Tier 3 share", "Share in deficit",
        "Deficit decay, % per day", "Reset period",
        "Buybacks 2024, $", "Buybacks 2025, $", "Buybacks 2026, $", "Total buybacks, $", "Days with purchases", "First purchase",
        "Budget at end, $", "Deepest deficit, $", "LDO bought, M", "DAO economic surplus for the period, $",
        "Profit coverage", "Overspend (buybacks in loss-making periods), $", "Buyback activations",
        "Conclusion / comment", "", "helper: fixed?", "helper: expense variant", "helper: as NEST?", "helper: deficit code", "helper: scale?", "helper: quarter?"]
hdr(v, 4, cols)
v["B3"] = "Parameters"; v["B3"].font = f_bold
v["Q3"] = "Dynamic scale"; v["Q3"].font = f_bold
v["W3"] = "Debt policy"; v["W3"].font = f_bold
v["Y3"] = "Results"; v["Y3"].font = f_bold
v["AG3"] = "Comparison metrics"; v["AG3"].font = f_bold
S0, S1 = date(2025, 1, 1), date(2026, 9, 28)
# name, type, fixed, exp_opt, mult, basis, share, deficit, scale, b1, b2, s2, s3, sneg
variants = [
 ("Current NEST", "fixed", 40e6, "all", 1, "as NEST", 0.5, "accumulates", 30, "no", 5e6, 15e6, 0.5, 0.5, 0.5, 0, "quarter"),
 ("Current + deficit does not accumulate", "fixed", 40e6, "all", 1, "as NEST", 0.5, "does not accumulate", 30, "no", 5e6, 15e6, 0.5, 0.5, 0.5, 0, "quarter"),
 ("Fixed threshold 35M, 50%", "fixed", 35e6, "all", 1, "as NEST", 0.5, "accumulates", 30, "no", 5e6, 15e6, 0.5, 0.5, 0.5, 0, "quarter"),
 ("Aksusarya proposal: 30M, 100%", "fixed", 30e6, "all", 1, "as NEST", 1.0, "accumulates", 30, "no", 5e6, 15e6, 1.0, 1.0, 1.0, 0, "quarter"),
 ("Threshold = all expenses, net, 100%, does not accumulate", "expenses", 40e6, "all", 1, "net", 1.0, "does not accumulate", 30, "no", 5e6, 15e6, 1.0, 1.0, 1.0, 0, "quarter"),
 ("Same with expenses −20%", "expenses", 40e6, "all", 0.8, "net", 1.0, "does not accumulate", 30, "no", 5e6, 15e6, 1.0, 1.0, 1.0, 0, "quarter"),
 ("Threshold = staking+shared, net, 100%", "expenses", 40e6, "staking+shared", 1, "net", 1.0, "does not accumulate", 30, "no", 5e6, 15e6, 1.0, 1.0, 1.0, 0, "quarter"),
 ("Threshold = staking only, net, 50%", "expenses", 40e6, "staking", 1, "net", 0.5, "does not accumulate", 30, "no", 5e6, 15e6, 0.5, 0.5, 0.5, 0, "quarter"),
 ("Scale at 40M threshold: 25% / 50% / 75%", "fixed", 40e6, "all", 1, "as NEST", 0.25, "accumulates", 30, "progressive", 5e6, 15e6, 0.5, 0.75, 0.5, 0, "quarter"),
 ("Scale on expenses, net: 50% / 75% / 100%", "expenses", 40e6, "all", 1, "net", 0.5, "does not accumulate", 30, "progressive", 5e6, 10e6, 0.75, 1.0, 0.5, 0, "quarter"),
 ("Threshold = all expenses, 100%: deficit accumulates", "expenses", 40e6, "all", 1, "net", 1.0, "accumulates", 30, "no", 5e6, 15e6, 1.0, 1.0, 1.0, 0, "quarter"),
 ("Threshold = all expenses, 100%: floor 90 days", "expenses", 40e6, "all", 1, "net", 1.0, "floor N days", 90, "no", 5e6, 15e6, 1.0, 1.0, 1.0, 0, "quarter"),
 ("Threshold = all expenses, 100%: decay 1% per day", "expenses", 40e6, "all", 1, "net", 1.0, "decay", 30, "no", 5e6, 15e6, 1.0, 1.0, 1.0, 0.01, "quarter"),
 ("Threshold = all expenses, 100%: reset by quarter", "expenses", 40e6, "all", 1, "net", 1.0, "reset by period", 30, "no", 5e6, 15e6, 1.0, 1.0, 1.0, 0, "quarter"),
 ("Threshold = all expenses, 100%: reset by year", "expenses", 40e6, "all", 1, "net", 1.0, "reset by period", 30, "no", 5e6, 15e6, 1.0, 1.0, 1.0, 0, "year"),
 ("Threshold = all expenses, 100%: window 90 days", "expenses", 40e6, "all", 1, "net", 1.0, "rolling window", 90, "no", 5e6, 15e6, 1.0, 1.0, 1.0, 0, "quarter"),
 ("Custom variant 1", "fixed", 40e6, "all", 1, "as NEST", 0.5, "accumulates", 30, "no", 5e6, 15e6, 0.5, 0.5, 0.5, 0, "quarter"),
 ("Custom variant 2", "fixed", 40e6, "all", 1, "as NEST", 0.5, "accumulates", 30, "no", 5e6, 15e6, 0.5, 0.5, 0.5, 0, "quarter"),
]
NV = len(variants)
FIRST, LASTV = 5, 4 + NV
for k, (name, bt, fb, eo, em, rb, sh, dm, nd, sc, b1, b2, s2, s3, sn, dc, rp) in enumerate(variants):
    r = FIRST + k
    v[f"A{r}"] = k + 1
    vals = [("B", name, None), ("C", S0, DT), ("D", S1, DT), ("E", bt, None), ("F", fb, USD), ("G", eo, None),
            ("H", em, "0.00"), ("I", rb, None), ("J", sh, "0%"), ("K", 50000, USD), ("L", 10000000, USD),
            ("M", 1000, USD), ("N", dm, None), ("O", nd, "0"), ("P", 0, USD),
            ("Q", sc, None), ("R", b1, USD), ("S", b2, USD), ("T", s2, "0%"), ("U", s3, "0%"), ("V", sn, "0%"),
            ("W", dc, "0.00%"), ("X", rp, None)]
    for col, val, fmt in vals: inp(v[f"{col}{r}"], val, fmt, key=True)
    v[f"AN{r}"] = f'=IF(E{r}="fixed",1,0)'
    v[f"AO{r}"] = f"=MATCH(G{r},Lists!$B$2:$B$4,0)"
    v[f"AP{r}"] = f'=IF(I{r}="as NEST",1,0)'
    v[f"AQ{r}"] = f"=MATCH(N{r},Lists!$D$2:$D$7,0)"
    v[f"AR{r}"] = f'=IF(Q{r}="progressive",1,0)'
    v[f"AS{r}"] = f'=IF(X{r}="quarter",1,0)'
for ref, rng in [("E", "$A$2:$A$3"), ("G", "$B$2:$B$4"), ("I", "$C$2:$C$3"), ("N", "$D$2:$D$7"), ("Q", "$E$2:$E$3"), ("X", "$F$2:$F$3")]:
    dv = DataValidation(type="list", formula1=f"=Lists!{rng}", allow_blank=False); v.add_data_validation(dv)
    dv.add(f"{ref}{FIRST}:{ref}{LASTV}")
v.freeze_panes = "C5"
wd = {"A": 4, "B": 40, "C": 11, "D": 11, "E": 10, "F": 13, "G": 15, "H": 10, "I": 11, "J": 10, "K": 11, "L": 13,
      "M": 10, "N": 15, "O": 8, "P": 13, "Q": 13, "R": 13, "S": 13, "T": 9, "U": 9, "V": 9, "W": 10, "X": 10,
      "Y": 13, "Z": 13, "AA": 13, "AB": 14, "AC": 9, "AD": 12, "AE": 14, "AF": 14, "AG": 10, "AH": 16, "AI": 11,
      "AJ": 16, "AK": 10, "AL": 50, "AM": 2, "AN": 8, "AO": 8, "AP": 8, "AQ": 8, "AR": 8, "AS": 8}
widths(v, wd)
v.row_dimensions[4].height = 58
note_r = LASTV + 2
v[f"A{note_r}"] = "How to read the parameters"; v[f"A{note_r}"].font = f_bold
notes = [
 "Threshold type: ‘fixed’ = fixed amount per year (F), ‘expenses’ = actual Foundations expenses by period from the Expenses sheet.",
 "Expenses for threshold: all Foundations expenses, staking together with shared services, or staking only. Multiplier 0.8 = expenses 20% below actual.",
 "Revenue base: ‘as NEST’ = treasury inflows before referral payouts, ‘net’ = after cost of revenue (as in Lido reports).",
 "Deficit (debt policy): ‘accumulates’ = as now in NEST; ‘floor N days’ = deficit no deeper than N days of threshold × share; ‘does not accumulate’ = deficit resets to zero every day; ‘decay’ = W% of the deficit is forgiven each day; ‘reset by period’ = deficit resets to zero at the start of each quarter or year (column X); ‘rolling window’ = buybacks come from the surplus sum minus buybacks over the last N days, and everything older is forgotten (both deficit and unspent surplus).",
 "Scale ‘no’: the entire surplus and deficit are multiplied by share J. Scale ‘progressive’: the surplus above the threshold is split into tiers. Up to bound 1 share J, between bounds 1 and 2 share T, above bound 2 share U. The deficit accumulates with share V.",
 "Scale bounds are set in dollars per year above the threshold; in the daily calculation they are divided by 365.",
 "Caps and minimum purchase default to the NEST contract values: $50k per day, $10M per 365-day window, $1,000. 0 in a cap column = no cap.",
 "Profit coverage = buybacks / DAO economic surplus (net revenue − all expenses) for the same period. Above 100% means buybacks exceed what was earned.",
 "Overspend = buybacks in periods (year or quarter from reports) when the DAO economic surplus was negative.",
 "LDO bought = buybacks per day / LDO price on the same day (DefiLlama). Activations = how many times buybacks started after a day with no purchases.",
]
for i, t in enumerate(notes, note_r + 1):
    v[f"A{i}"] = t; v[f"A{i}"].font = f_norm

# ---------------- Engine ----------------
en = wb.create_sheet("Engine")
E0 = 3; ELAST = E0 + N - 1
en["A1"] = "Daily calculation"; en["A1"].font = f_bold
hdr(en, 2, ["Date", "Year", "Period #", "Treasury inflow, $", "DAO economic surplus/day, $", "Period in loss", "LDO/USD", "Quarter key"])
for i in range(E0, ELAST + 1):
    dr = i - 1
    en[f"A{i}"] = f"=Data!A{dr}"; en[f"A{i}"].number_format = DT
    en[f"B{i}"] = f"=YEAR(A{i})"
    en[f"C{i}"] = f"=MATCH(A{i},Expenses!$B$5:$B$9,1)"
    en[f"D{i}"] = f"=Data!E{dr}"; en[f"D{i}"].number_format = USD
    en[f"E{i}"] = f"=D{i}*(1-INDEX(Expenses!$J$5:$J$9,C{i}))-INDEX(Expenses!$K$5:$K$9,C{i})"; en[f"E{i}"].number_format = USD
    en[f"F{i}"] = f"=IF(INDEX(Expenses!$P$5:$P$9,C{i})<0,1,0)"
    en[f"G{i}"] = f"=Data!L{dr}"; en[f"G{i}"].number_format = "0.0000"
    en[f"H{i}"] = f"=B{i}*10+ROUNDUP(MONTH(A{i})/3,0)"
BLOCK = ["Active", "Revenue used", "Baseline/day", "Surplus", "Delta", "Budget pre-policy", "Budget after policy",
         "Cap window", "Spent in window before", "Buy", "Budget end", "Cum delta", "Cum buy"]
C0 = 10
for k in range(NV):
    vr = FIRST + k
    c0 = C0 + k * (len(BLOCK) + 1)
    L = {nm: CL(c0 + j) for j, nm in enumerate(BLOCK)}
    en.cell(row=1, column=c0, value=f"=\"Variant {k+1}: \"&Variants!$B${vr}").font = f_bold
    hdr(en, 2, BLOCK, col=c0)
    V = lambda col: f"Variants!${col}${vr}"
    a, rv, bs, su, de, pre, fl, wi, sp, by, ed, cd, cb = [L[n] for n in BLOCK]
    CDR = f"${cd}${E0}:${cd}${ELAST}"; CBR = f"${cb}${E0}:${cb}${ELAST}"
    for i in range(E0, ELAST + 1):
        p = i - 1
        en[f"{a}{i}"] = f"=IF(AND($A{i}>={V('C')},$A{i}<={V('D')}),1,0)"
        en[f"{rv}{i}"] = f"=IF({V('AP')}=1,$D{i},$D{i}*(1-INDEX(Expenses!$J$5:$J$9,$C{i})))"
        en[f"{bs}{i}"] = f"=IF({V('AN')}=1,{V('F')}/365,INDEX(Expenses!$K$5:$M$9,$C{i},{V('AO')})*{V('H')})"
        en[f"{su}{i}"] = f"={rv}{i}-{bs}{i}"
        dyn = (f"IF({su}{i}>=0,{V('J')}*MIN({su}{i},{V('R')}/365)+{V('T')}*MIN(MAX({su}{i}-{V('R')}/365,0),"
               f"MAX({V('S')}-{V('R')},0)/365)+{V('U')}*MAX({su}{i}-{V('S')}/365,0),{V('V')}*{su}{i})")
        en[f"{de}{i}"] = f"=IF({a}{i}=1,IF({V('AR')}=1,{dyn},{V('J')}*{su}{i}),0)"
        if i == E0:
            prevadj = V('P')
        else:
            prev = f"IF({a}{p}=1,{ed}{p},{V('P')})"
            newp = f"IF({V('AS')}=1,$H{i}<>$H{p},$B{i}<>$B{p})"
            prevadj = f"IF(AND({V('AQ')}=5,{newp}),MAX(0,{prev}),{prev})"
        en[f"{pre}{i}"] = f"=IF({a}{i}=1,{prevadj}+{de}{i},0)"
        negshare = f"IF({V('AR')}=1,{V('V')},{V('J')})"
        nd = V('O')
        cdn = f"IF({i}-{nd}<{E0},0,INDEX({CDR},{i}-{nd}-{E0}+1))"
        cbn = f"IF({i}-{nd}<{E0},0,INDEX({CBR},{i}-{nd}-{E0}+1))"
        cbp = "0" if i == E0 else f"{cb}{p}"
        window = f"({cd}{i}-{cdn})-({cbp}-{cbn})"
        en[f"{fl}{i}"] = (f"=IF({a}{i}=1,CHOOSE({V('AQ')},{pre}{i},MAX({pre}{i},-{nd}*{bs}{i}*{negshare}),MAX(0,{pre}{i}),"
                          f"IF({pre}{i}<0,{pre}{i}*(1-{V('W')}),{pre}{i}),{pre}{i},{window}),0)")
        en[f"{wi}{i}"] = f"=IF({a}{i}=1,INT(($A{i}-{V('C')})/365),-1)"
        en[f"{sp}{i}"] = "=0" if i == E0 else f"=IF(AND({a}{i}=1,{wi}{i}={wi}{p}),{sp}{p}+{by}{p},0)"
        en[f"{by}{i}"] = (f"=IF(AND({a}{i}=1,{fl}{i}>{V('M')}),MAX(0,MIN({fl}{i},IF({V('K')}>0,{V('K')},1E+18),"
                          f"IF({V('L')}>0,{V('L')}-{sp}{i},1E+18))),0)")
        en[f"{ed}{i}"] = f"={fl}{i}-{by}{i}"
        en[f"{cd}{i}"] = f"={de}{i}" if i == E0 else f"={cd}{p}+{de}{i}"
        en[f"{cb}{i}"] = f"={by}{i}" if i == E0 else f"={cb}{p}+{by}{i}"
        for col in (rv, bs, su, de, pre, fl, sp, by, ed, cd, cb): en[f"{col}{i}"].number_format = USD
    for j in range(len(BLOCK)): en.column_dimensions[CL(c0 + j)].width = 13
    en.column_dimensions[CL(c0 + len(BLOCK))].width = 2
    EA = f"Engine!$A${E0}:$A${ELAST}"; EB = f"Engine!$B${E0}:$B${ELAST}"
    BY = f"Engine!${by}${E0}:${by}${ELAST}"; ED = f"Engine!${ed}${E0}:${ed}${ELAST}"
    ACT = f"Engine!${a}${E0}:${a}${ELAST}"
    for col, y in (("Y", 2024), ("Z", 2025), ("AA", 2026)):
        v[f"{col}{vr}"] = f"=SUMIFS({BY},{EB},{y})"; v[f"{col}{vr}"].number_format = USD
    v[f"AB{vr}"] = f"=SUM(Y{vr}:AA{vr})"; v[f"AB{vr}"].number_format = USD; v[f"AB{vr}"].font = f_bold
    v[f"AC{vr}"] = f'=COUNTIF({BY},">0")'
    v[f"AD{vr}"] = f'=IF(AC{vr}>0,_xlfn.MINIFS({EA},{BY},">0"),"no")'; v[f"AD{vr}"].number_format = DT
    v[f"AE{vr}"] = f"=INDEX({ED},MATCH(D{vr},{EA},0))"; v[f"AE{vr}"].number_format = USD
    v[f"AF{vr}"] = f"=MIN({ED})"; v[f"AF{vr}"].number_format = USD
    v[f"AG{vr}"] = f"=SUMPRODUCT({BY}/Engine!$G${E0}:$G${ELAST})/1000000"; v[f"AG{vr}"].number_format = "0.00"
    v[f"AH{vr}"] = f"=SUMIFS(Engine!$E${E0}:$E${ELAST},{ACT},1)"; v[f"AH{vr}"].number_format = USD
    v[f"AI{vr}"] = f'=IF(AH{vr}>0,AB{vr}/AH{vr},"no profit")'; v[f"AI{vr}"].number_format = "0%"
    v[f"AJ{vr}"] = f"=SUMIFS({BY},Engine!$F${E0}:$F${ELAST},1)"; v[f"AJ{vr}"].number_format = USD
    v[f"AK{vr}"] = (f"=IF(Engine!{by}{E0}>0,1,0)+SUMPRODUCT((Engine!{by}{E0+1}:{by}{ELAST}>0)*"
                    f"(Engine!{by}{E0}:{by}{ELAST-1}=0))")
en.column_dimensions["A"].width = 11; en.column_dimensions["D"].width = 14; en.column_dimensions["E"].width = 14
en.freeze_panes = "I3"
# ---------------- NEST_check ----------------
n = wb.create_sheet("NEST_check")
n["A1"] = "Reproduction of the NEST onchain budget at checkpoints"; n["A1"].font = f_title
n["A2"] = "Contract formula: budget = share × (counter revenue − daily threshold × number of daily slots). Slots are counted from the activation day inclusive through the checkpoint day inclusive."; n["A2"].font = f_note
n["A4"] = "NEST activation (activationTS)"; inp(n["B4"], date(2026, 8, 10), DT)
n["A5"] = "Daily threshold, $ (reserveDailyRateUSD)"; inp(n["B5"], 109589, USD)
n["A6"] = "Share (surplusShareBP)"; inp(n["B6"], 0.5, "0%")
n["A7"] = "First rebase captured by the counter"; inp(n["B7"], date(2026, 8, 15), DT)
n["C4"] = "Source: BuybackAllocator 0xAA568141c051f2D1132b110f8391F18D48E8D889, StakingRevenueSource 0x6220212a33a87Ed7Cc386B67eB2c393974F28C38"; n["C4"].font = f_note
hdr(n, 9, ["Checkpoint date", "Block", "Tx hash", "NEST revenue counter, $", "NEST onchain budget, $", "Slots",
           "Budget by formula, $", "Error, $", "Our revenue for the same rebases, $", "Budget on our revenue, $", "Difference from onchain, %"])
cps = list(csv.DictReader(open("base/nest_checkpoints.csv")))
for i, c in enumerate(cps, 10):
    dt = date.fromisoformat(c["ts"][:10])
    n[f"A{i}"] = dt; n[f"A{i}"].number_format = DT
    n[f"B{i}"] = int(c["block"]); n[f"C{i}"] = c["tx"]
    inp(n[f"D{i}"], float(c["totalRevenueUSD"]), USD2); inp(n[f"E{i}"], float(c["budgetUSD"]), USD2)
    n[f"F{i}"] = f"=A{i}-$B$4+1"
    n[f"G{i}"] = f"=$B$6*(D{i}-$B$5*F{i})"; n[f"G{i}"].number_format = USD2
    n[f"H{i}"] = f"=G{i}-E{i}"; n[f"H{i}"].number_format = USD2
    n[f"I{i}"] = f'=SUMIFS({DE},{DA},">="&$B$7,{DA},"<"&A{i})'; n[f"I{i}"].number_format = USD2
    n[f"J{i}"] = f"=$B$6*(I{i}-$B$5*F{i})"; n[f"J{i}"].number_format = USD2
    n[f"K{i}"] = f"=IF(D{i}>0,I{i}/D{i}-1,0)"; n[f"K{i}"].number_format = PCT
lastn = 9 + len(cps)
n[f"A{lastn+2}"] = "Maximum formula error, $"; n[f"B{lastn+2}"] = f"=MAX(MAX(H10:H{lastn}),-MIN(H10:H{lastn}))"
n[f"B{lastn+2}"].number_format = USD2
n[f"A{lastn+3}"] = "Latest NEST budget, $"; n[f"B{lastn+3}"] = f"=E{lastn}"; n[f"B{lastn+3}"].number_format = USD2
widths(n, {"A": 36, "B": 12, "C": 68, "D": 20, "E": 20, "F": 8, "G": 20, "H": 12, "I": 22, "J": 22, "K": 12})
NEST_LAST_BUDGET = f"NEST_check!$B${lastn+3}"

# ---------------- Recon ----------------
rc = wb.create_sheet("Recon")
rc["A1"] = "True-up of onchain inflows against Lido reports"; rc["A1"].font = f_title
hdr(rc, 3, ["Period", "Start", "End", "Onchain treasury inflows, $", "Report: net staking revenue, $", "Difference, $",
            "Report: referral payouts, $", "Residual, $", "Report: total protocol fee, $", "Treasury share of fee", "Source"])
recon = [
 ("2024", date(2024,1,1), date(2024,12,31), 48500000, 3100000, None, "GOOSE-2025 Final Report (t/11304)"),
 ("2025", date(2025,1,1), date(2025,12,31), 37400000, 4100000, None, "GOOSE-2025 Final Report (t/11304)"),
 ("Q1 2026", date(2026,1,1), date(2026,3,31), 8630000, None, 14990000, "H1 2026 Report, P&L"),
 ("Q2 2026", date(2026,4,1), date(2026,6,30), 7080000, None, 12520000, "H1 2026 Report, P&L"),
 ("H1 2026", date(2026,1,1), date(2026,6,30), 15710000, None, 27510000, "H1 2026 Report, P&L"),
]
for i, (lab, a, b, net, ref, gross, src) in enumerate(recon, 4):
    rc[f"A{i}"] = lab; rc[f"B{i}"] = a; rc[f"C{i}"] = b
    rc[f"B{i}"].number_format = DT; rc[f"C{i}"].number_format = DT
    rc[f"D{i}"] = f'=SUMIFS({DE},{DA},">="&B{i},{DA},"<="&C{i})'
    inp(rc[f"E{i}"], net, USD)
    rc[f"F{i}"] = f"=D{i}-E{i}"
    if ref is not None:
        inp(rc[f"G{i}"], ref, USD); rc[f"H{i}"] = f"=F{i}-G{i}"
    else:
        rc[f"G{i}"] = "not disclosed"; rc[f"H{i}"] = "n/a"
    if gross is not None:
        inp(rc[f"I{i}"], gross, USD); rc[f"J{i}"] = f"=D{i}/I{i}"; rc[f"J{i}"].number_format = PCT
    rc[f"K{i}"] = src; rc[f"K{i}"].font = f_note
    for c in "DFH": rc[f"{c}{i}"].number_format = USD
rc["A10"] = "The 2024/2025 residual is within report rounding ($0.1M) and the difference in valuation methods (report at end-of-day price, onchain at block price)."; rc["A10"].font = f_note
rc["A11"] = "The H1 2026 difference is cost of revenue: under Lido's methodology, referral payouts and possibly operator discounts; there is no breakdown for H1."; rc["A11"].font = f_note
widths(rc, {"A": 10, "B": 12, "C": 12, "D": 22, "E": 22, "F": 14, "G": 18, "H": 12, "I": 20, "J": 12, "K": 36})

# ---------------- Forward ----------------
fw = wb.create_sheet("Forward")
fw["A1"] = "12-month scenarios: revenue = TVL × yield × DAO share × ETH price"; fw["A1"].font = f_title
fw["A3"] = "Calibration to actual data"; fw["A3"].font = f_bold
fw["A4"] = "Average treasury inflows over 30 days, stETH/day"
fw["B4"] = f'=AVERAGEIFS({DB},{DA},">"&(MAX({DA})-30))'; fw["B4"].number_format = "0.00"
fw["A5"] = "Latest ETH/USD price"; fw["B5"] = f"=INDEX({DD},MATCH(MAX({DA}),{DA},0))"; fw["B5"].number_format = "#,##0.00"
fw["A6"] = "DAO share of rewards"; inp(fw["B6"], 0.0617, PCT, key=True)
fw["C6"] = "StakingRouter getStakingFeeAggregateDistributionE4Precision(), 28.09.2026"; fw["C6"].font = f_note
fw["A7"] = "Lido TVL, M ETH"; inp(fw["B7"], 9.13, "0.00", key=True)
fw["C7"] = "H1 2026 Report, 30.06.2026, with entry queue; the implied yield below is calibrated so that revenue matches actuals"; fw["C7"].font = f_note
fw["A8"] = "Implied gross staking yield"; fw["B8"] = "=B4*365/(B6*B7*1000000)"; fw["B8"].number_format = PCT
fw["A9"] = "Current NEST budget, $"; fw["B9"] = f"={NEST_LAST_BUDGET}"; fw["B9"].number_format = USD; fw["B9"].font = f_link
fw["A10"] = "Annual cap, $"; inp(fw["B10"], 10000000, USD)
fw["A11"] = "Share for expense-based rule"; inp(fw["B11"], 1.0, "0%", key=True)

hdr(fw, 13, ["Metric", "Now", "Team targets (23% share)", "ETH $2,000", "ETH $3,500", "Issuance −30%", "Move to Curated v2 (5.8%)"])
cols = "BCDEFG"
fw["A14"] = "TVL, M ETH"; fw["A15"] = "Gross yield"; fw["A16"] = "DAO share"; fw["A17"] = "ETH price, $"
fw["A18"] = "Cost of revenue share"; fw["A19"] = "Foundations expenses, $ per year"; fw["A20"] = "NEST fixed threshold, $"
for c in cols:
    fw[f"{c}14"] = "=$B$7"; fw[f"{c}15"] = "=$B$8"; fw[f"{c}16"] = "=$B$6"; fw[f"{c}17"] = "=$B$5"
    fw[f"{c}18"] = "=Expenses!$B$16"; fw[f"{c}19"] = "=Expenses!$B$13"
    fw[f"{c}20"] = 40000000; fw[f"{c}20"].font = f_in
fw["C14"] = "=$B$7*23/21.2"
fw["D17"] = 2000; fw["D17"].font = f_in; fw["D17"].fill = fill_in
fw["E17"] = 3500; fw["E17"].font = f_in; fw["E17"].fill = fill_in
fw["F15"] = "=$B$8*0.7"
fw["G16"] = 0.058; fw["G16"].font = f_in; fw["G16"].fill = fill_in
fw["A22"] = "Results"; fw["A22"].font = f_bold
labels = {23: "Treasury inflows, $ per year", 24: "Net staking revenue, $ per year",
          25: "Break-even ETH price for the NEST threshold", 26: "ETH price at which net revenue = expenses",
          27: "Buybacks under current rule (50%, cap), $ per year", 28: "Days to pay off current deficit (current rule)",
          29: "Buybacks: threshold = expenses, net revenue, share B11, $ per year", 30: "Buybacks: proposal 30M / 100%, $ per year"}
for r, t in labels.items(): fw[f"A{r}"] = t
for c in cols:
    fw[f"{c}23"] = f"={c}14*1000000*{c}15*{c}16*{c}17"
    fw[f"{c}24"] = f"={c}23*(1-{c}18)"
    fw[f"{c}25"] = f"={c}20/({c}14*1000000*{c}15*{c}16)"
    fw[f"{c}26"] = f"={c}19/({c}14*1000000*{c}15*{c}16*(1-{c}18))"
    fw[f"{c}27"] = f"=MIN($B$10,0.5*MAX(0,{c}23-{c}20))"
    fw[f"{c}28"] = f'=IF({c}23>{c}20,-$B$9/(0.5*({c}23-{c}20)/365),"not paid off")'
    fw[f"{c}29"] = f"=MIN($B$10,$B$11*MAX(0,{c}24-{c}19))"
    fw[f"{c}30"] = f"=MIN($B$10,MAX(0,{c}23-30000000))"
    for r in (19, 20, 23, 24, 27, 29, 30): fw[f"{c}{r}"].number_format = USD
    for r in (25, 26, 17): fw[f"{c}{r}"].number_format = "$#,##0"
    fw[f"{c}14"].number_format = "0.00"; fw[f"{c}15"].number_format = PCT; fw[f"{c}16"].number_format = PCT; fw[f"{c}18"].number_format = PCT
    fw[f"{c}28"].number_format = "#,##0"
fw["A32"] = "Simplifications: flat revenue for the year ahead, the daily cap does not bind ($50k × 365 > $10M), the deficit is paid off only in row 28."; fw["A32"].font = f_note
widths(fw, {"A": 58, "B": 16, "C": 18, "D": 14, "E": 14, "F": 14, "G": 20})

# ---------------- Grid_Python ----------------
gp = wb.create_sheet("Grid_Python")
gp["A1"] = "Scenario grid from the Python model (simulator.py) on the same base, ending 28.09.2026. Values, not formulas."; gp["A1"].font = f_bold
grid = list(csv.reader(open("results_grid_base.csv")))
hdr(gp, 3, grid[0])
for i, r in enumerate(grid[1:], 4):
    for j, v in enumerate(r, 1):
        try: v = float(v) if j >= 3 and j <= 8 else v
        except ValueError: pass
        c = gp.cell(row=i, column=j, value=v); c.font = f_norm
        if 3 <= j <= 7: c.number_format = USD
widths(gp, {"A": 13, "B": 32, "C": 14, "D": 14, "E": 14, "F": 14, "G": 14, "H": 12, "I": 12})

for ws in wb.worksheets:
    for row in ws.iter_rows():
        for c in row:
            if c.value is not None and c.font.name != F:
                c.font = Font(name=F, size=10, bold=bool(c.font.bold), italic=bool(c.font.italic), color=(c.font.color.rgb if c.font.color is not None and isinstance(c.font.color.rgb, str) else None))

wb.save("../nest_model.xlsx")
print("saved")
