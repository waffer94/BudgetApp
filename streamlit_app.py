"""Household budget for two people.

Personal categories sit with one person, shared categories split by an
adjustable percentage, and each balance is income minus (own costs +
share of shared costs).

Every entry also records whose account the money moved through, which is
what the settle-up figure is built from: bearing a cost and paying for it
are different things.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

import store as store_mod

INK, MUTED, LINE = "#16302C", "#6E7F79", "#D3DDD4"
A_COL, S_COL, SHARED, GOOD, BAD = "#A8506A", "#2E6D8C", "#A5762C", "#2C7A5A", "#A6413B"

st.set_page_config(page_title="Household Budget", page_icon="◧", layout="wide")

st.markdown(f"""
<style>
  .block-container {{ padding-top: 2.2rem; max-width: 1100px; }}
  .eyebrow {{ font-size: .70rem; letter-spacing: .16em; text-transform: uppercase;
              color: {MUTED}; margin-bottom: .35rem; }}
  .tile {{ background: #fff; border: 1px solid {LINE}; border-radius: 10px;
           padding: 1rem 1.1rem; height: 100%; }}
  .tile.dark {{ background: {INK}; border-color: {INK}; color: #EEF2EC; text-align: center; }}
  .tile .big {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                font-size: 1.7rem; line-height: 1.2; margin: .3rem 0; }}
  .tile .row {{ display: flex; justify-content: space-between; font-size: .78rem;
                color: {MUTED}; }}
  .tile .row span:last-child {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  .settle {{ background: #fff; border: 1px solid {LINE}; border-left: 4px solid {SHARED};
             border-radius: 10px; padding: .85rem 1.1rem; margin-top: .9rem; }}
  .settle .amt {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 600; }}
  .cat {{ margin-bottom: .55rem; }}
  .cat .top {{ display: flex; justify-content: space-between; align-items: baseline;
               font-size: .88rem; gap: .75rem; }}
  .cat .amt {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
               font-size: .8rem; color: {MUTED}; white-space: nowrap; }}
  .cat .track {{ height: 6px; border-radius: 99px; background: #EEF2EC; margin-top: .3rem; }}
  .cat .fill {{ height: 100%; border-radius: 99px; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- helpers
def money(n) -> str:
    n = round(float(n))
    return ("-$" if n < 0 else "$") + f"{abs(n):,}"


def month_key(d: dt.date) -> str:
    return f"{d.year}-{d.month:02d}"


def shift_month(key: str, n: int) -> str:
    y, m = (int(x) for x in key.split("-"))
    total = y * 12 + (m - 1) + n
    return f"{total // 12}-{total % 12 + 1:02d}"


def month_label(key: str) -> str:
    y, m = (int(x) for x in key.split("-"))
    return dt.date(y, m, 1).strftime("%B %Y")


def bar(name: str, actual: float, budget: float, colour: str, inflow=False) -> str:
    pct = min(actual / budget, 1.0) * 100 if budget > 0 else 0
    bad = (0 < actual < budget) if inflow else (actual > budget)
    fill = BAD if bad else colour
    amt_col = BAD if bad else MUTED
    return (f'<div class="cat"><div class="top"><span>{name}</span>'
            f'<span class="amt" style="color:{amt_col}">{money(actual)} / {money(budget)}</span></div>'
            f'<div class="track"><div class="fill" style="width:{pct:.1f}%;background:{fill}"></div>'
            f'</div></div>')


# ------------------------------------------------------------------ data
store = store_mod.get_store()


def load():
    st.session_state.cats = store.read_categories()
    st.session_state.settings = store.read_settings()
    st.session_state.txns = store.read_txns()


if "cats" not in st.session_state:
    load()
if "nonce" not in st.session_state:
    st.session_state.nonce = 0

cats = st.session_state.cats
settings = st.session_state.settings
txns = st.session_state.txns

PEOPLE = [
    {"id": "aishwarya", "name": "Aishwarya", "income": settings.get("income_aishwarya", 0), "colour": A_COL},
    {"id": "shriniwas", "name": "Shriniwas", "income": settings.get("income_shriniwas", 0), "colour": S_COL},
]
IDS = [p["id"] for p in PEOPLE]
SHARE_A = settings.get("split_pct", 50) / 100
SHARES = {"aishwarya": SHARE_A, "shriniwas": 1 - SHARE_A}
NAME = {p["id"]: p["name"] for p in PEOPLE} | {"common": "Shared"}
PAYER_LABEL = {p["id"]: p["name"] for p in PEOPLE} | {"common": "Each their own share"}


# ---------------------------------------------------------------- sidebar
months = sorted({t["date"][:7] for t in txns if len(t.get("date", "")) >= 7}
                | {shift_month(month_key(dt.date.today()), i) for i in range(-11, 2)},
                reverse=True)

with st.sidebar:
    st.markdown('<div class="eyebrow">Month</div>', unsafe_allow_html=True)
    this_month = month_key(dt.date.today())
    month = st.selectbox("Month", months, format_func=month_label, label_visibility="collapsed",
                         index=months.index(this_month) if this_month in months else 0)
    st.divider()
    if st.button("Reload from source"):
        load()
        st.rerun()
    st.caption(f"Saving to: **{store.label}**")
    if store.label == "Local file":
        st.warning("No sheet configured, so this is a local file. On Community Cloud "
                   "that data disappears when the app restarts.", icon="⚠️")


# ----------------------------------------------------------------- maths
def allocation(t: dict, by_id: dict) -> dict:
    """How a single entry is shared out, regardless of who paid for it."""
    c = by_id.get(t.get("cat_id"))
    owner = c["owner"] if c else (t.get("who") or "common")
    if owner == "common":
        return {i: SHARES[i] for i in IDS}
    return {i: (1.0 if i == owner else 0.0) for i in IDS}


def compute(month: str) -> dict:
    by_id = {c["id"]: c for c in cats}
    rows = [t for t in txns if t.get("date", "").startswith(month)]

    spent: dict[str, float] = {}
    got: dict[str, float] = {}
    for t in rows:
        if t.get("cat_id"):
            spent[t["cat_id"]] = spent.get(t["cat_id"], 0) + t["amount"]
        if t["kind"] == "income":
            got[t.get("who") or "common"] = got.get(t.get("who") or "common", 0) + t["amount"]

    # Settle-up: what each person put in, against what each person owes.
    put_in = {i: 0.0 for i in IDS}
    owes = {i: 0.0 for i in IDS}
    for t in rows:
        alloc = allocation(t, by_id)
        payer = t.get("paid_by") or "common"
        sign = -1 if t["kind"] == "income" else 1  # income is a negative cost
        for i in IDS:
            owes[i] += sign * alloc[i] * t["amount"]
        if payer in IDS:
            put_in[payer] += sign * t["amount"]
        else:
            for i in IDS:
                put_in[i] += sign * alloc[i] * t["amount"]
    net = {i: put_in[i] - owes[i] for i in IDS}

    live = [dict(c, actual=spent.get(c["id"], 0)) for c in cats]
    outs = [c for c in live if c["flow"] != "in"]
    ins = [c for c in live if c["flow"] == "in"]
    total = lambda lst, k: sum(c[k] for c in lst)

    common_out = [c for c in outs if c["owner"] == "common"]
    common_in = [c for c in ins if c["owner"] == "common"]
    cb, ca = total(common_out, "budget"), total(common_out, "actual")
    cib = total(common_in, "budget")

    people = []
    for p in PEOPLE:
        share = SHARES[p["id"]]
        mine = [c for c in outs if c["owner"] == p["id"]]
        mine_in = [c for c in ins if c["owner"] == p["id"]]
        budget = total(mine, "budget") + cb * share
        actual = total(mine, "actual") + ca * share
        income = p["income"] + got.get(p["id"], 0) + got.get("common", 0) * share
        planned_income = p["income"] + total(mine_in, "budget") + cib * share
        people.append(dict(p, share=share, cats=mine, budget=budget, actual=actual,
                           income=income, planned=planned_income - budget,
                           balance=income - actual, put_in=put_in[p["id"]], net=net[p["id"]]))

    return {"rows": rows, "ins": ins, "common": common_out, "people": people, "net": net,
            "income": sum(p["income"] for p in people),
            "actual": sum(p["actual"] for p in people)}


m = compute(month)
pa, ps = m["people"]

st.markdown('<div class="eyebrow">Shared household ledger</div>', unsafe_allow_html=True)
st.title(f"{pa['name']} & {ps['name']}")

tab_dash, tab_ledger, tab_budget = st.tabs(["Dashboard", "Ledger", "Budget"])


# ------------------------------------------------------------- dashboard
with tab_dash:
    c1, c2, c3 = st.columns(3)
    for col, p in ((c1, pa), (c3, ps)):
        col.markdown(
            f'<div class="tile" style="border-top:3px solid {p["colour"]}">'
            f'<div class="eyebrow" style="color:{p["colour"]}">{p["name"]}</div>'
            f'<div class="big" style="color:{GOOD if p["balance"] >= 0 else BAD}">{money(p["balance"])}</div>'
            f'<div class="row"><span>Income</span><span>{money(p["income"])}</span></div>'
            f'<div class="row"><span>Cost borne</span><span>{money(p["actual"])}</span></div>'
            f'<div class="row"><span>Actually paid out</span><span>{money(p["put_in"])}</span></div>'
            f'<div class="row"><span>Planned out</span><span>{money(p["budget"])}</span></div>'
            f'</div>', unsafe_allow_html=True)
    c2.markdown(
        f'<div class="tile dark"><div class="eyebrow" style="color:#9FB3AC">Together</div>'
        f'<div class="big">{money(m["income"] - m["actual"])}</div>'
        f'<div style="font-size:.78rem;opacity:.75">{money(m["actual"])} spent of {money(m["income"])}</div>'
        f'</div>', unsafe_allow_html=True)

    # settle up
    owed_to = max(IDS, key=lambda i: m["net"][i])
    owed_by = min(IDS, key=lambda i: m["net"][i])
    gap = m["net"][owed_to]
    if round(gap) <= 0:
        settle = "Nothing to settle this month — everything was paid by whoever bore it."
    else:
        settle = (f'<span>{NAME[owed_by]}</span> owes <span>{NAME[owed_to]}</span> '
                  f'<span class="amt">{money(gap)}</span> to square up.')
    st.markdown(f'<div class="settle"><div class="eyebrow" style="color:{SHARED}">Settle up</div>'
                f'<div style="font-size:.95rem">{settle}</div></div>', unsafe_allow_html=True)

    if m["actual"] > m["income"]:
        st.error(f"Spending is ahead of income this month by {money(m['actual'] - m['income'])}.", icon="▲")

    st.write("")
    head, btn = st.columns([3, 1])
    head.subheader("Where the month is going")
    if btn.button("Post fixed items"):
        done = {t.get("cat_id") for t in m["rows"] if t.get("cat_id")}
        new = []
        for c in cats:
            if not c.get("fixed") or c["id"] in done:
                continue
            payer = c.get("payer") or ("common" if c["owner"] == "common" else c["owner"])
            if c["flow"] == "in":
                new.append({"id": store_mod.new_id(), "date": f"{month}-01", "kind": "income",
                            "cat_id": c["id"], "who": c["owner"], "amount": c["budget"],
                            "note": c["name"], "paid_by": payer})
            else:
                new.append({"id": store_mod.new_id(), "date": f"{month}-01", "kind": "expense",
                            "cat_id": c["id"], "who": "", "amount": c["budget"],
                            "note": "Fixed bill", "paid_by": payer})
        if not new:
            st.info("Fixed items are already posted for this month.")
        else:
            store.add_txns(new)
            st.session_state.txns.extend(new)
            st.rerun()

    if m["ins"]:
        st.markdown(f'<div class="eyebrow" style="color:{GOOD}">Money in, beyond salary</div>',
                    unsafe_allow_html=True)
        cols = st.columns(2)
        for i, c in enumerate(m["ins"]):
            cols[i % 2].markdown(bar(c["name"], c["actual"], c["budget"], GOOD, inflow=True),
                                 unsafe_allow_html=True)
        st.divider()

    left, right = st.columns(2)
    for col, p in ((left, pa), (right, ps)):
        col.markdown(f'<div class="eyebrow" style="color:{p["colour"]}">{p["name"]}</div>',
                     unsafe_allow_html=True)
        if not p["cats"]:
            col.caption("No personal categories yet.")
        for c in p["cats"]:
            col.markdown(bar(c["name"], c["actual"], c["budget"], p["colour"]), unsafe_allow_html=True)

    st.divider()
    st.markdown(f'<div class="eyebrow" style="color:{SHARED}">Shared · split '
                f'{round(SHARE_A * 100)} / {round((1 - SHARE_A) * 100)}</div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for i, c in enumerate(m["common"]):
        cols[i % 2].markdown(bar(c["name"], c["actual"], c["budget"], SHARED), unsafe_allow_html=True)

    st.write("")
    st.subheader("Last six months")
    trend = []
    for i in range(5, -1, -1):
        k = shift_month(month, -i)
        rows = [t for t in txns if t.get("date", "").startswith(k)]
        trend.append({
            "Month": k,
            "Income": sum(p["income"] for p in PEOPLE) + sum(t["amount"] for t in rows if t["kind"] == "income"),
            "Spent": sum(t["amount"] for t in rows if t["kind"] == "expense"),
        })
    st.bar_chart(pd.DataFrame(trend).set_index("Month"), stack=False, color=[A_COL, GOOD], height=260)


# ---------------------------------------------------------------- ledger
with tab_ledger:
    out_cats = [c for c in cats if c["flow"] != "in"]
    in_cats = [c for c in cats if c["flow"] == "in"]
    default_day = min(dt.date.today().day, 28)
    y, mo = (int(x) for x in month.split("-"))
    n = st.session_state.nonce  # bump to reset the inputs after an entry

    kind = st.radio("Entry type", ["Expense", "Income"], horizontal=True,
                    label_visibility="collapsed", key=f"kind_{n}")

    c1, c2, c3, c4, c5 = st.columns([1.1, 1.9, 1.3, 1, 1.4])
    date = c1.date_input("Date", value=dt.date(y, mo, default_day), key=f"date_{n}")

    if kind == "Expense":
        pick = c2.selectbox("Category", out_cats, key=f"cat_{n}",
                            format_func=lambda c: f"{c['name']} · {NAME.get(c['owner'], c['owner'])}")
        suggested = (pick or {}).get("payer") or "common"
        payer_label = "Paid by"
    else:
        options = ([("cat", c) for c in in_cats]
                   + [("who", p) for p in PEOPLE]
                   + [("who", {"id": "common", "name": "Shared"})])
        pick = c2.selectbox("Source", options, key=f"src_{n}",
                            format_func=lambda o: (f"{o[1]['name']} · {NAME.get(o[1].get('owner'), '')}"
                                                   if o[0] == "cat" else f"One-off · {o[1]['name']}"))
        suggested = (pick[1].get("payer") if pick[0] == "cat" else "common") or "common"
        payer_label = "Received by"

    # Whose account the money moved through. Defaults to whatever the category
    # says, so the common case is one click.
    payer_opts = IDS + ["common"]
    paid_by = c3.selectbox(payer_label, payer_opts, key=f"payer_{n}",
                           index=payer_opts.index(suggested) if suggested in payer_opts else len(payer_opts) - 1,
                           format_func=lambda i: PAYER_LABEL[i])
    amount = c4.number_input("Amount", min_value=0.0, step=10.0, format="%.2f", key=f"amt_{n}")
    note = c5.text_input("Note", placeholder="Optional", key=f"note_{n}")

    if st.button(f"Add {kind.lower()}", type="primary") and amount > 0:
        if kind == "Expense":
            row = {"id": store_mod.new_id(), "date": str(date), "kind": "expense",
                   "cat_id": pick["id"], "who": "", "amount": amount,
                   "note": note, "paid_by": paid_by}
        elif pick[0] == "cat":
            c = pick[1]
            row = {"id": store_mod.new_id(), "date": str(date), "kind": "income",
                   "cat_id": c["id"], "who": c["owner"], "amount": amount,
                   "note": note or c["name"], "paid_by": paid_by}
        else:
            row = {"id": store_mod.new_id(), "date": str(date), "kind": "income",
                   "cat_id": "", "who": pick[1]["id"], "amount": amount,
                   "note": note or "Extra income", "paid_by": paid_by}
        store.add_txns([row])
        st.session_state.txns.append(row)
        st.session_state.nonce += 1
        st.rerun()

    st.subheader(month_label(month))
    by_id = {c["id"]: c for c in cats}
    rows = sorted(m["rows"], key=lambda t: t["date"], reverse=True)

    if not rows:
        st.caption("Nothing recorded yet. Add an entry above, or post the fixed items from the dashboard.")
    for t in rows:
        c1, c2, c3, c4, c5 = st.columns([1, 4, 1.4, 1.2, 0.6])
        c1.markdown(f'<span style="font-family:ui-monospace;color:{MUTED};font-size:.8rem">'
                    f'{t["date"][5:]}</span>', unsafe_allow_html=True)
        cat = by_id.get(t.get("cat_id"))
        if cat:
            label = f"{cat['name']} · {NAME.get(cat['owner'], cat['owner'])}"
        else:
            label = f"Income · {NAME.get(t.get('who'), t.get('who'))}"
        if t.get("note"):
            label += f" — {t['note']}"
        c2.markdown(f'<span style="font-size:.88rem">{label}</span>', unsafe_allow_html=True)
        payer = t.get("paid_by") or "common"
        verb = "got" if t["kind"] == "income" else "paid"
        payer_txt = f"{verb} by {NAME[payer]}" if payer in IDS else "split at source"
        c3.markdown(f'<span style="font-size:.78rem;color:{MUTED}">{payer_txt}</span>',
                    unsafe_allow_html=True)
        sign = "+" if t["kind"] == "income" else ""
        c4.markdown(f'<span style="font-family:ui-monospace;font-size:.85rem;'
                    f'color:{GOOD if t["kind"] == "income" else INK}">{sign}{money(t["amount"])}</span>',
                    unsafe_allow_html=True)
        if c5.button("✕", key=f"del{t['id']}", help="Delete entry"):
            kept = [x for x in txns if x["id"] != t["id"]]
            store.write_txns(kept)
            st.session_state.txns = kept
            st.rerun()


# ---------------------------------------------------------------- budget
with tab_budget:
    st.subheader("Monthly income")
    c1, c2, c3 = st.columns(3)
    inc_a = c1.number_input("Aishwarya", value=float(settings.get("income_aishwarya", 0)), step=50.0)
    inc_s = c2.number_input("Shriniwas", value=float(settings.get("income_shriniwas", 0)), step=50.0)
    split = c3.slider("Aishwarya's share of shared costs (%)", 0, 100,
                      int(settings.get("split_pct", 50)), step=5)
    if st.button("Save income and split"):
        new = {"income_aishwarya": inc_a, "income_shriniwas": inc_s, "split_pct": split}
        store.write_settings(new)
        st.session_state.settings = new
        st.rerun()

    st.divider()
    st.subheader("Categories")
    st.caption("Direction decides the maths: money out counts against the budget, money in adds "
               "to income. Usually paid by pre-fills the ledger and drives Post fixed items — set "
               "it to *Each their own share* for anything you each pay separately.")

    df = pd.DataFrame(cats)[["id", "name", "owner", "flow", "type", "budget", "fixed", "payer"]]
    edited = st.data_editor(
        df, num_rows="dynamic", hide_index=True, key="cat_editor",
        column_config={
            "id": None,
            "name": st.column_config.TextColumn("Category", required=True),
            "owner": st.column_config.SelectboxColumn("Whose", options=["aishwarya", "shriniwas", "common"], required=True),
            "flow": st.column_config.SelectboxColumn("Direction", options=["out", "in"], required=True),
            "type": st.column_config.TextColumn("Type"),
            "budget": st.column_config.NumberColumn("Monthly", format="$%d", min_value=0, step=10),
            "fixed": st.column_config.CheckboxColumn("Fixed"),
            "payer": st.column_config.SelectboxColumn("Usually paid by", options=["aishwarya", "shriniwas", "common"]),
        },
    )

    if st.button("Save categories", type="primary"):
        out = []
        for r in edited.to_dict("records"):
            if not str(r.get("name") or "").strip():
                continue
            out.append({
                "id": str(r.get("id") or "").strip() or store_mod.new_id(),
                "name": str(r["name"]).strip(),
                "owner": r.get("owner") or "common",
                "flow": "in" if r.get("flow") == "in" else "out",
                "type": str(r.get("type") or ""),
                "budget": float(r.get("budget") or 0),
                "fixed": bool(r.get("fixed")),
                "payer": r.get("payer") or "common",
            })
        store.write_categories(out)
        st.session_state.cats = out
        st.rerun()

    st.divider()
    totals = {o: sum(c["budget"] for c in cats if c["owner"] == o and c["flow"] != "in")
              for o in ("aishwarya", "shriniwas", "common")}
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Aishwarya out", money(totals["aishwarya"]))
    t2.metric("Shared out", money(totals["common"]))
    t3.metric("Shriniwas out", money(totals["shriniwas"]))
    t4.metric("Extra in", money(sum(c["budget"] for c in cats if c["flow"] == "in")))

st.caption(f"{month_label(month)} · data in {store.label}")
