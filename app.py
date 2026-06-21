# ============================================================
#  Ignite Energy Access Nigeria — Sales Agent Map
#  Python Dash app  |  app.py  (v4 — PostgreSQL backend)
#
#  Install dependencies (run once):
#  pip install dash==2.9.3 dash-bootstrap-components==1.4.1
#             plotly==5.13.1 pandas==1.5.3 pydantic==1.10.7
#             psycopg2-binary gunicorn
#
#  Run:  python app.py
#  Then open http://127.0.0.1:8050
# ============================================================

import os
import pandas as pd
import plotly.graph_objects as go
import psycopg2
from psycopg2.extras import RealDictCursor
import dash
from dash import dcc, html, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import math
import json

# ── Database connection ───────────────────────────────────────
DB_CONFIG = {
    "host":     os.environ.get("DB_HOST",     "localhost"),
    "port":     os.environ.get("DB_PORT",     "5432"),
    "dbname":   os.environ.get("DB_NAME",     "ignite_agents"),
    "user":     os.environ.get("DB_USER",     "postgres"),
    "password": os.environ.get("DB_PASSWORD", "mankind"),
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def load_agents():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM agents ORDER BY id")
            rows = cur.fetchall()
    return [dict(r) for r in rows]

def upsert_agent(a):
    """Insert or update agent. If id is None, insert; else update."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            if a.get("id"):
                cur.execute("""
                    UPDATE agents SET
                        name=%s, state=%s, region=%s, status=%s, star=%s,
                        rev=%s, rev_target=%s, lat=%s, lon=%s, rec=%s
                    WHERE id=%s
                """, (a["name"], a["state"], a["region"], a["status"], a["star"],
                      a["rev"], a["rev_target"], a["lat"], a["lon"], a["rec"], a["id"]))
            else:
                cur.execute("""
                    INSERT INTO agents (name,state,region,status,star,rev,rev_target,lat,lon,rec)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
                """, (a["name"], a["state"], a["region"], a["status"], a["star"],
                      a["rev"], a["rev_target"], a["lat"], a["lon"], a["rec"]))
        conn.commit()

def delete_agent(agent_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM agents WHERE id=%s", (agent_id,))
        conn.commit()

# ── Monthly trend seed data ───────────────────────────────────
TREND_DATA = {
    "Amara Okafor":    [88e6, 95e6, 102e6, 110e6, 121e6, 132e6],
    "Tunde Adeyemi":   [70e6, 68e6, 65e6,  63e6,  61e6,  62e6],
    "Funmi Olatunji":  [18e6, 20e6, 22e6,  24e6,  26e6,  28e6],
    "Ibrahim Musa":    [20e6, 21e6, 20e6,  22e6,  21e6,  22e6],
    "Chukwudi Eze":    [22e6, 21e6, 20e6,  19e6,  18e6,  18e6],
    "Ngozi Obi":       [16e6, 17e6, 17e6,  18e6,  19e6,  19e6],
    "Biodun Faleyimu": [12e6, 13e6, 13e6,  14e6,  14e6,  14e6],
}
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun"]

# ── Helpers ──────────────────────────────────────────────────
def fmt_rev(v):
    if not v:    return "—"
    if v >= 1e9: return f"₦{v/1e9:.1f}B"
    return f"₦{v/1e6:.0f}M"

def attainment(rev, target):
    if not target: return None
    return round(rev / target * 100, 1)

def attainment_color(pct):
    if pct is None: return "#888"
    if pct >= 100:  return "#1D9E75"
    if pct >= 75:   return "#F59E0B"
    return "#E24B4A"

def dot_color(star, status):
    if star:                  return "#F59E0B"
    if status == "Priority":  return "#E24B4A"
    if status == "Active":    return "#1D9E75"
    return "#888888"

def bubble_size(rev, max_rev=132092776, min_s=8, max_s=36):
    if not rev: return min_s
    return min_s + (max_s - min_s) * math.sqrt(rev / max_rev)

def build_figure(df):
    fig = go.Figure()
    for _, a in df.iterrows():
        color   = dot_color(a["star"], a["status"])
        size    = bubble_size(a["rev"])
        fill_op = 0.0 if a["status"] == "Vacant" else 0.82
        sym     = "circle-open" if a["status"] == "Vacant" else "circle"
        pct     = attainment(a["rev"], a["rev_target"])
        pct_str = f"{pct}% of target" if pct is not None else "No target set"
        hover   = (
            f"<b>{a['name']}</b>{'  ⭐' if a['star'] else ''}<br>"
            f"<span style='color:#888'>{a['state']} · {a['region']}</span><br>"
            f"<b style='color:#1A5276'>{fmt_rev(a['rev'])}{'/ mo' if a['rev'] else ''}</b>"
            f" vs target {fmt_rev(a['rev_target'])}<br>"
            f"Attainment: <b>{pct_str}</b><br>"
            f"Status: {a['status']}<br><i>{a['rec']}</i>"
        )
        fig.add_trace(go.Scattergeo(
            lon=[a["lon"]], lat=[a["lat"]],
            mode="markers+text",
            marker=dict(size=size, color=color,
                        opacity=fill_op if a["status"] != "Vacant" else 1,
                        line=dict(color=color, width=2 if a["star"] else 1.5),
                        symbol=sym),
            text=[a["state"] if a["status"] in ("Active","Priority") else ""],
            textposition="top center",
            textfont=dict(size=9, color=color, family="Arial"),
            hovertemplate=hover + "<extra></extra>",
            name=a["name"], showlegend=False,
        ))
    fig.update_layout(
        geo=dict(scope="africa", center=dict(lon=8.0, lat=9.0),
                 projection_scale=6.5, showland=True, landcolor="#D6EAF8",
                 showocean=True, oceancolor="#EBF5FB",
                 showcountries=True, countrycolor="#B5D4F4", showframe=False),
        margin=dict(l=0,r=0,t=0,b=0),
        paper_bgcolor="white", height=460,
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial"),
    )
    return fig

def build_target_chart(df):
    active = df[df["status"]=="Active"].copy()
    if active.empty: return go.Figure()
    active["pct"] = active.apply(lambda r: attainment(r["rev"], r["rev_target"]), axis=1)
    active = active.dropna(subset=["pct"]).sort_values("pct", ascending=True)
    colors = [attainment_color(p) for p in active["pct"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=active["name"], x=active["pct"], orientation="h",
        marker_color=colors,
        text=[f"{p}%" for p in active["pct"]], textposition="outside",
        hovertemplate="<b>%{y}</b><br>Attainment: %{x}%<extra></extra>",
    ))
    fig.add_vline(x=100, line_dash="dash", line_color="#1A5276", line_width=1.5,
                  annotation_text="Target", annotation_position="top")
    fig.update_layout(
        title=dict(text="Revenue attainment vs. target (%)",
                   font_size=13, font_color="#1A5276", x=0),
        xaxis=dict(title="% of target", range=[0, max(150, active["pct"].max()+20)]),
        yaxis=dict(title=""),
        margin=dict(l=10,r=60,t=40,b=30),
        paper_bgcolor="white", plot_bgcolor="#F8F9FA",
        height=280, font=dict(family="Arial", size=11),
    )
    return fig

def build_trend_chart(data):
    fig = go.Figure()
    agent_map = {a["name"]: a["rev_target"] for a in data}
    for name, values in TREND_DATA.items():
        target = agent_map.get(name, 0)
        fig.add_trace(go.Scatter(
            x=MONTHS, y=values, mode="lines+markers", name=name.split()[0],
            hovertemplate=f"<b>{name}</b><br>%{{x}}: ₦%{{y:,.0f}}<extra></extra>",
            line=dict(width=2),
        ))
        if target:
            fig.add_trace(go.Scatter(
                x=MONTHS, y=[target]*6, mode="lines",
                name=f"{name.split()[0]} target",
                line=dict(dash="dot", width=1), showlegend=False,
                hovertemplate=f"Target: ₦{target:,.0f}<extra></extra>",
            ))
    fig.update_layout(
        title=dict(text="Monthly revenue trend — active agents (Jan–Jun 2026)",
                   font_size=13, font_color="#1A5276", x=0),
        xaxis=dict(title=""),
        yaxis=dict(title="Monthly Revenue (₦)", tickformat=",.0f"),
        margin=dict(l=10,r=10,t=40,b=30),
        paper_bgcolor="white", plot_bgcolor="#F8F9FA",
        height=300, font=dict(family="Arial", size=11),
        legend=dict(orientation="h", y=-0.2),
    )
    return fig

def build_table(df):
    rows = []
    for _, a in df.iterrows():
        pct = attainment(a["rev"], a["rev_target"])
        pct_display = (
            html.Span(f"{pct}%", style={
                "background": attainment_color(pct), "color":"white",
                "padding":"2px 8px","borderRadius":"10px",
                "fontSize":"11px","fontWeight":"600"})
            if pct is not None else html.Span("—", style={"color":"#aaa"})
        )
        rows.append(html.Tr([
            html.Td(("⭐ " if a["star"] else "") + a["name"],
                    style={"fontSize":"12px","fontWeight":"600","padding":"7px 10px"}),
            html.Td(a["state"],   style={"fontSize":"11px","color":"#555","padding":"7px 8px"}),
            html.Td(a["region"],  style={"fontSize":"11px","color":"#555","padding":"7px 8px"}),
            html.Td(html.Span(a["status"], style={
                "background":{"Active":"#D1FAE5","Priority":"#FEE2E2","Vacant":"#F3F4F6"}.get(a["status"],"#eee"),
                "padding":"2px 8px","borderRadius":"10px","fontSize":"11px"})),
            html.Td(fmt_rev(a["rev"]),        style={"fontSize":"12px","fontWeight":"600","color":"#1A5276","padding":"7px 8px"}),
            html.Td(fmt_rev(a["rev_target"]), style={"fontSize":"11px","color":"#888","padding":"7px 8px"}),
            html.Td(pct_display, style={"padding":"7px 8px"}),
            html.Td(a["rec"],    style={"fontSize":"11px","color":"#666","maxWidth":"200px","padding":"7px 8px"}),
            html.Td([
                dbc.Button("✏", id={"type":"btn-edit","index": int(a["id"])},
                           color="link", size="sm",
                           style={"color":"#1A5276","fontSize":"14px","padding":"0 6px"}),
                dbc.Button("✕", id={"type":"btn-del","index": int(a["id"])},
                           color="link", size="sm",
                           style={"color":"#E24B4A","fontSize":"14px","padding":"0 6px"}),
            ], style={"padding":"7px 6px","whiteSpace":"nowrap"}),
        ], style={"borderBottom":"1px solid #eee"}))
    return rows

# ── App ──────────────────────────────────────────────────────
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY],
                suppress_callback_exceptions=True)
app.title = "Ignite Nigeria — Sales Agent Map"
server = app.server

CARD = {"background":"#fff","border":"1px solid #ddd","borderRadius":"8px",
        "padding":"10px 14px","textAlign":"center","marginBottom":"8px"}

def metric_card(label, val_id):
    return dbc.Col(html.Div([
        html.Div(label, style={"fontSize":"11px","color":"#888"}),
        html.Div("—", id=val_id,
                 style={"fontSize":"22px","fontWeight":"700","color":"#1A5276"}),
    ], style=CARD))

app.layout = dbc.Container([
    # Refresh store — triggers DB reload
    dcc.Store(id="refresh-trigger", data=0),
    dcc.Store(id="editing-id", data=None),
    dcc.Store(id="del-id",     data=None),

    html.H4("Ignite Energy Access Nigeria — Sales Agent Map",
            style={"color":"#1A5276","fontWeight":"600","marginTop":"16px"}),
    html.P("Regional coverage, revenue performance & hiring priorities · June 2026",
           style={"fontSize":"12px","color":"#888","marginBottom":"16px"}),

    dbc.Row([
        metric_card("Active agents",       "m-active"),
        metric_card("Monthly revenue",     "m-rev"),
        metric_card("Total target",        "m-target"),
        metric_card("Portfolio attainment","m-attain"),
        metric_card("Vacant territories",  "m-vacant"),
        metric_card("Priority hires",      "m-priority"),
    ], className="mb-3"),

    dbc.Row([
        dbc.Col(dbc.RadioItems(
            id="filter-status",
            options=[{"label":l,"value":v} for l,v in
                     [("All","All"),("Active","Active"),("Vacant","Vacant"),("Priority hire","Priority")]],
            value="All", inline=True,
        ), width=5),
        dbc.Col(dbc.Input(id="search", placeholder="🔍  Search name / state…",
                          type="text", size="sm"), width=3),
        dbc.Col([
            dbc.Button("＋ Add agent",  id="btn-add",    color="success",         size="sm", className="me-2"),
            dbc.Button("⬇ Export CSV", id="btn-export", color="outline-primary", size="sm"),
            dcc.Download(id="download-csv"),
        ], width=4, className="d-flex align-items-center justify-content-end"),
    ], className="mb-2 align-items-center"),

    html.Div([
        html.Span("🟡 Star performer  "),
        html.Span("🟢 Active  "),
        html.Span("🔴 Priority hire  "),
        html.Span("⚪ Vacant  "),
        html.Span("● bubble size = revenue", style={"color":"#aaa"}),
    ], style={"fontSize":"12px","color":"#555","marginBottom":"8px"}),

    dbc.Card(dcc.Graph(id="map", config={"displayModeBar":False}),
             className="mb-3", style={"border":"1px solid #ddd"}),

    dbc.Row([
        dbc.Col(dbc.Card(dcc.Graph(id="target-chart", config={"displayModeBar":False}),
                         style={"border":"1px solid #ddd","padding":"10px"}), width=5),
        dbc.Col(dbc.Card(dcc.Graph(id="trend-chart",  config={"displayModeBar":False}),
                         style={"border":"1px solid #ddd","padding":"10px"}), width=7),
    ], className="mb-3"),

    html.H6("Agent details — click ✏ to edit or ✕ to remove",
            style={"color":"#1A5276","fontWeight":"600"}),
    html.Div(html.Table([
        html.Thead(html.Tr([
            html.Th(c, style={"fontSize":"11px","color":"white","background":"#1A5276",
                              "padding":"8px 10px","fontWeight":"600"})
            for c in ["Name","State","Region","Status","Revenue","Target","Attainment","Notes","Actions"]
        ])),
        html.Tbody(id="agent-tbody"),
    ], style={"width":"100%","borderCollapse":"collapse","border":"1px solid #ddd"}),
    style={"overflowX":"auto","marginBottom":"40px"}),

    # ── Add/Edit Modal ──────────────────────────────────────
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(id="modal-title")),
        dbc.ModalBody([
            dbc.Row([
                dbc.Col([dbc.Label("Name",  style={"fontSize":"12px"}),
                         dbc.Input(id="f-name",  type="text", size="sm")], width=6),
                dbc.Col([dbc.Label("State", style={"fontSize":"12px"}),
                         dbc.Input(id="f-state", type="text", size="sm")], width=6),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([dbc.Label("Region", style={"fontSize":"12px"}),
                         dbc.Input(id="f-region", type="text", size="sm")], width=6),
                dbc.Col([dbc.Label("Status", style={"fontSize":"12px"}),
                         dbc.Select(id="f-status", size="sm",
                             options=[{"label":"Active","value":"Active"},
                                      {"label":"Priority","value":"Priority"},
                                      {"label":"Vacant","value":"Vacant"}])], width=6),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([dbc.Label("Star performer?", style={"fontSize":"12px"}),
                         dbc.Select(id="f-star", size="sm",
                             options=[{"label":"No","value":"False"},
                                      {"label":"Yes","value":"True"}])], width=6),
                dbc.Col([dbc.Label("Monthly revenue (₦)", style={"fontSize":"12px"}),
                         dbc.Input(id="f-rev", type="number", min=0, step=1000000, size="sm")], width=6),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([dbc.Label("Monthly target (₦)", style={"fontSize":"12px"}),
                         dbc.Input(id="f-rev-target", type="number", min=0, step=1000000, size="sm")], width=6),
                dbc.Col([dbc.Label("", style={"fontSize":"12px"}),
                         html.Div(id="f-attain-preview",
                                  style={"fontSize":"12px","marginTop":"6px","color":"#555"})], width=6),
            ], className="mb-2"),
            dbc.Row([
                dbc.Col([dbc.Label("Latitude",  style={"fontSize":"12px"}),
                         dbc.Input(id="f-lat", type="number", step=0.001, size="sm")], width=6),
                dbc.Col([dbc.Label("Longitude", style={"fontSize":"12px"}),
                         dbc.Input(id="f-lon", type="number", step=0.001, size="sm")], width=6),
            ], className="mb-2"),
            dbc.Label("Recommendation / notes", style={"fontSize":"12px"}),
            dbc.Textarea(id="f-rec", rows=2, style={"fontSize":"12px"}),
            html.Div(id="modal-error",
                     style={"color":"#E24B4A","fontSize":"12px","marginTop":"6px"}),
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="btn-cancel", color="secondary", size="sm", className="me-2"),
            dbc.Button("Save",   id="btn-save",   color="primary",   size="sm"),
        ]),
    ], id="modal", is_open=False),

    # ── Delete Modal ────────────────────────────────────────
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Remove agent?")),
        dbc.ModalBody(html.P(id="del-msg", style={"fontSize":"13px"})),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="btn-del-cancel",  color="secondary", size="sm", className="me-2"),
            dbc.Button("Remove", id="btn-del-confirm", color="danger",    size="sm"),
        ]),
    ], id="del-modal", is_open=False),

], fluid=True, style={"fontFamily":"Arial"})


# ── Callbacks ────────────────────────────────────────────────

def apply_filters(data, status_filter, search):
    df = pd.DataFrame(data)
    if status_filter and status_filter != "All":
        df = df[df["status"] == status_filter]
    if search:
        q = search.lower()
        df = df[df.apply(
            lambda r: q in r["name"].lower() or
                      q in r["state"].lower() or
                      q in r["region"].lower(), axis=1)]
    return df


@app.callback(
    Output("map",          "figure"),
    Output("target-chart", "figure"),
    Output("trend-chart",  "figure"),
    Output("agent-tbody",  "children"),
    Output("m-active",     "children"),
    Output("m-rev",        "children"),
    Output("m-target",     "children"),
    Output("m-attain",     "children"),
    Output("m-vacant",     "children"),
    Output("m-priority",   "children"),
    Input("refresh-trigger","data"),
    Input("filter-status", "value"),
    Input("search",        "value"),
)
def refresh(trigger, status_filter, search):
    data   = load_agents()
    df     = apply_filters(data, status_filter or "All", search or "")
    active = df[df["status"]=="Active"]
    vacant = df[df["status"]=="Vacant"]
    pri    = df[df["status"]=="Priority"]
    total_rev    = int(active["rev"].sum())
    total_target = int(active["rev_target"].sum())
    pct          = attainment(total_rev, total_target)
    pct_str      = f"{pct}%" if pct else "—"
    return (
        build_figure(df),
        build_target_chart(df),
        build_trend_chart(data),
        build_table(df),
        str(len(active)),
        fmt_rev(total_rev),
        fmt_rev(total_target),
        html.Span(pct_str, style={"color": attainment_color(pct)}),
        str(len(vacant)),
        str(len(pri)),
    )


# Attainment preview
@app.callback(
    Output("f-attain-preview","children"),
    Input("f-rev",       "value"),
    Input("f-rev-target","value"),
)
def preview_attainment(rev, target):
    if not rev or not target or target == 0: return ""
    pct = round(rev / target * 100, 1)
    return html.Span(f"Attainment: {pct}%",
                     style={"color": attainment_color(pct), "fontWeight":"600"})


# Open Add modal
@app.callback(
    Output("modal",        "is_open",  allow_duplicate=True),
    Output("modal-title",  "children", allow_duplicate=True),
    Output("editing-id",   "data",     allow_duplicate=True),
    Output("f-name",       "value",    allow_duplicate=True),
    Output("f-state",      "value",    allow_duplicate=True),
    Output("f-region",     "value",    allow_duplicate=True),
    Output("f-status",     "value",    allow_duplicate=True),
    Output("f-star",       "value",    allow_duplicate=True),
    Output("f-rev",        "value",    allow_duplicate=True),
    Output("f-rev-target", "value",    allow_duplicate=True),
    Output("f-lat",        "value",    allow_duplicate=True),
    Output("f-lon",        "value",    allow_duplicate=True),
    Output("f-rec",        "value",    allow_duplicate=True),
    Output("modal-error",  "children", allow_duplicate=True),
    Input("btn-add","n_clicks"),
    prevent_initial_call=True,
)
def open_add(_):
    return True,"Add new agent / territory",None,"","","","Active","False",0,0,9.0,7.5,"",""


# Open Edit modal
@app.callback(
    Output("modal",        "is_open",  allow_duplicate=True),
    Output("modal-title",  "children", allow_duplicate=True),
    Output("editing-id",   "data",     allow_duplicate=True),
    Output("f-name",       "value",    allow_duplicate=True),
    Output("f-state",      "value",    allow_duplicate=True),
    Output("f-region",     "value",    allow_duplicate=True),
    Output("f-status",     "value",    allow_duplicate=True),
    Output("f-star",       "value",    allow_duplicate=True),
    Output("f-rev",        "value",    allow_duplicate=True),
    Output("f-rev-target", "value",    allow_duplicate=True),
    Output("f-lat",        "value",    allow_duplicate=True),
    Output("f-lon",        "value",    allow_duplicate=True),
    Output("f-rec",        "value",    allow_duplicate=True),
    Output("modal-error",  "children", allow_duplicate=True),
    Input({"type":"btn-edit","index":dash.ALL},"n_clicks"),
    State("refresh-trigger","data"),
    prevent_initial_call=True,
)
def open_edit(n_clicks, trigger):
    from dash import callback_context
    if not any(n for n in n_clicks if n):
        return [no_update]*14
    triggered = callback_context.triggered[0]["prop_id"]
    agent_id  = json.loads(triggered.split(".")[0])["index"]
    data = load_agents()
    a = next((x for x in data if x["id"] == agent_id), None)
    if not a: return [no_update]*14
    return (True, "Edit agent", agent_id,
            a["name"], a["state"], a["region"], a["status"],
            str(a["star"]), a["rev"], a.get("rev_target",0),
            a["lat"], a["lon"], a["rec"], "")


# Save agent → write to DB → trigger refresh
@app.callback(
    Output("refresh-trigger","data",    allow_duplicate=True),
    Output("modal",          "is_open", allow_duplicate=True),
    Output("modal-error",    "children",allow_duplicate=True),
    Input("btn-save","n_clicks"),
    State("refresh-trigger","data"),
    State("editing-id",    "data"),
    State("f-name",        "value"),
    State("f-state",       "value"),
    State("f-region",      "value"),
    State("f-status",      "value"),
    State("f-star",        "value"),
    State("f-rev",         "value"),
    State("f-rev-target",  "value"),
    State("f-lat",         "value"),
    State("f-lon",         "value"),
    State("f-rec",         "value"),
    prevent_initial_call=True,
)
def save_agent(_, trigger, editing_id, name, state, region, status,
               star, rev, rev_target, lat, lon, rec):
    if not name or not state or lat is None or lon is None:
        return no_update, no_update, "⚠ Please fill in Name, State, Latitude and Longitude."
    upsert_agent(dict(
        id         = editing_id,
        name       = name,
        state      = state,
        region     = region,
        status     = status,
        star       = (str(star) == "True"),
        rev        = int(rev or 0),
        rev_target = int(rev_target or 0),
        lat        = lat,
        lon        = lon,
        rec        = rec or "",
    ))
    return (trigger or 0) + 1, False, ""


# Cancel modal
@app.callback(
    Output("modal","is_open",allow_duplicate=True),
    Input("btn-cancel","n_clicks"),
    prevent_initial_call=True,
)
def cancel_modal(_): return False


# Open delete modal
@app.callback(
    Output("del-modal","is_open", allow_duplicate=True),
    Output("del-id",   "data",    allow_duplicate=True),
    Output("del-msg",  "children",allow_duplicate=True),
    Input({"type":"btn-del","index":dash.ALL},"n_clicks"),
    prevent_initial_call=True,
)
def open_del(n_clicks):
    from dash import callback_context
    if not any(n for n in n_clicks if n):
        return no_update, no_update, no_update
    triggered = callback_context.triggered[0]["prop_id"]
    agent_id  = json.loads(triggered.split(".")[0])["index"]
    data = load_agents()
    a = next((x for x in data if x["id"] == agent_id), None)
    msg = f"This will permanently remove {a['name']}." if a else "Remove this agent?"
    return True, agent_id, msg


# Confirm delete → write to DB → trigger refresh
@app.callback(
    Output("refresh-trigger","data",    allow_duplicate=True),
    Output("del-modal",      "is_open", allow_duplicate=True),
    Input("btn-del-confirm","n_clicks"),
    State("del-id",          "data"),
    State("refresh-trigger", "data"),
    prevent_initial_call=True,
)
def confirm_delete(_, del_id, trigger):
    if del_id is None: return no_update, False
    delete_agent(del_id)
    return (trigger or 0) + 1, False


# Cancel delete
@app.callback(
    Output("del-modal","is_open",allow_duplicate=True),
    Input("btn-del-cancel","n_clicks"),
    prevent_initial_call=True,
)
def cancel_del(_): return False


# Export CSV
@app.callback(
    Output("download-csv","data"),
    Input("btn-export","n_clicks"),
    prevent_initial_call=True,
)
def export_csv(_):
    df = pd.DataFrame(load_agents()).drop(columns=["id"])
    return dcc.send_data_frame(df.to_csv, "ignite_agents.csv", index=False)


# ── Run ──────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run_server(debug=False, port=8050)
