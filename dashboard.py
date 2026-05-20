import os
import sqlite3

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from analysis import get_baseline_subset, get_frequency_table, get_responder_comparison

# Database connection helper
DB_PATH = os.path.join(os.path.dirname(__file__), "cell_trial.db")

if not os.path.exists(DB_PATH):
    raise FileNotFoundError(
        f"Database not found at {DB_PATH}.\n"
        "Please run  python load_data.py  first."
    )


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Load data once at startup
with get_conn() as conn:
    freq_df              = get_frequency_table(conn)
    resp_freq_df, stats_df = get_responder_comparison(conn)
    baseline             = get_baseline_subset(conn)

POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]
POP_LABELS = {
    "b_cell":      "B Cell",
    "cd8_t_cell":  "CD8 T Cell",
    "cd4_t_cell":  "CD4 T Cell",
    "nk_cell":     "NK Cell",
    "monocyte":    "Monocyte",
}

# Colour palette
COLOURS = {
    "primary":   "#2563EB",
    "secondary": "#7C3AED",
    "accent":    "#059669",
    "yes":       "#10B981",
    "no":        "#EF4444",
    "bg":        "#F8FAFC",
    "card":      "#FFFFFF",
    "border":    "#E2E8F0",
    "text":      "#1E293B",
    "muted":     "#64748B",
}

CARD_STYLE = {
    "background": COLOURS["card"],
    "border":     f"1px solid {COLOURS['border']}",
    "borderRadius": "8px",
    "padding":    "20px",
    "marginBottom": "16px",
    "boxShadow":  "0 1px 3px rgba(0,0,0,0.08)",
}

# Helper: DataTable defaults
def make_table(df: pd.DataFrame, table_id: str, page_size: int = 15) -> dash_table.DataTable:
    return dash_table.DataTable(
        id=table_id,
        columns=[{"name": c, "id": c} for c in df.columns],
        data=df.to_dict("records"),
        page_size=page_size,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "fontFamily": "Inter, system-ui, sans-serif",
            "fontSize":   "13px",
            "padding":    "8px 12px",
            "textAlign":  "left",
            "border":     f"1px solid {COLOURS['border']}",
            "color":      COLOURS["text"],
        },
        style_header={
            "backgroundColor": COLOURS["primary"],
            "color":           "#FFFFFF",
            "fontWeight":      "600",
            "border":          f"1px solid {COLOURS['primary']}",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#F1F5F9"},
        ],
    )


# Tab 1 — Data Overview (Part 2)
all_samples    = sorted(freq_df["sample"].unique())
all_populations = POPULATIONS

tab1_layout = html.Div([
    html.Div([
        html.H3("Cell Population Frequencies", style={"margin": "0 0 4px", "color": COLOURS["text"]}),
        html.P(
            "Relative frequency (%) of each immune cell population per sample. "
            "Use the filters below to narrow the view.",
            style={"color": COLOURS["muted"], "margin": 0, "fontSize": "14px"},
        ),
    ], style=CARD_STYLE),

    # Filter row
    html.Div([
        html.Div([
            html.Label("Filter by population", style={"fontWeight": "600", "fontSize": "13px", "marginBottom": "6px", "display": "block"}),
            dcc.Dropdown(
                id="pop-filter",
                options=[{"label": POP_LABELS[p], "value": p} for p in POPULATIONS],
                multi=True,
                placeholder="All populations",
                style={"fontSize": "13px"},
            ),
        ], style={"flex": "1", "minWidth": "220px"}),

        html.Div([
            html.Label("Percentage range (%)", style={"fontWeight": "600", "fontSize": "13px", "marginBottom": "6px", "display": "block"}),
            dcc.RangeSlider(
                id="pct-range",
                min=0, max=100, step=1,
                value=[0, 100],
                marks={0: "0", 25: "25", 50: "50", 75: "75", 100: "100"},
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ], style={"flex": "2", "minWidth": "260px"}),
    ], style={"display": "flex", "gap": "24px", "flexWrap": "wrap", **CARD_STYLE}),

    html.Div(id="freq-table-container"),
], style={"padding": "8px"})


@callback(
    Output("freq-table-container", "children"),
    Input("pop-filter", "value"),
    Input("pct-range", "value"),
)
def update_freq_table(pop_filter, pct_range):
    df = freq_df.copy()
    if pop_filter:
        df = df[df["population"].isin(pop_filter)]
    df = df[(df["percentage"] >= pct_range[0]) & (df["percentage"] <= pct_range[1])]
    df["population"] = df["population"].map(POP_LABELS)
    df["percentage"]  = df["percentage"].round(2)
    return html.Div([
        html.P(f"Showing {len(df):,} rows", style={"color": COLOURS["muted"], "fontSize": "13px", "marginBottom": "8px"}),
        make_table(df, "freq-table"),
    ], style=CARD_STYLE)


# Tab 2 — Responder Analysis (Part 3)
def build_boxplot() -> go.Figure:
    fig = go.Figure()
    groups = {"yes": ("Responders", COLOURS["yes"]), "no": ("Non-responders", COLOURS["no"])}

    for resp_val, (label, colour) in groups.items():
        sub = resp_freq_df[resp_freq_df["response"] == resp_val]
        fig.add_trace(go.Box(
            x=[POP_LABELS[p] for p in sub["population"]],
            y=sub["percentage"],
            name=label,
            marker_color=colour,
            boxmean="sd",
            line={"width": 1.5},
        ))

    fig.update_layout(
        boxmode="group",
        title={
            "text": "Cell Population Frequencies: Responders vs Non-responders<br>"
                    "<sup>Melanoma patients treated with miraclib — PBMC samples</sup>",
            "x": 0.5, "xanchor": "center",
            "font": {"size": 15, "color": COLOURS["text"]},
        },
        xaxis_title="Cell Population",
        yaxis_title="Relative Frequency (%)",
        legend={"title": "Response", "bgcolor": "rgba(0,0,0,0)"},
        paper_bgcolor=COLOURS["bg"],
        plot_bgcolor=COLOURS["bg"],
        font={"family": "Inter, system-ui, sans-serif", "color": COLOURS["text"]},
        margin={"t": 80, "b": 60},
        height=480,
    )
    fig.update_xaxes(gridcolor=COLOURS["border"])
    fig.update_yaxes(gridcolor=COLOURS["border"])
    return fig


def build_stats_table() -> dash_table.DataTable:
    display = stats_df.copy()
    display["population"] = display["population"].map(POP_LABELS)
    display = display.rename(columns={
        "population":       "Population",
        "n_responders":     "N (resp.)",
        "n_non_responders": "N (non-resp.)",
        "median_resp":      "Median % (resp.)",
        "median_nonresp":   "Median % (non-resp.)",
        "U_statistic":      "U statistic",
        "p_value":          "p-value",
        "significant":      "p < 0.05?",
    })
    return dash_table.DataTable(
        columns=[{"name": c, "id": c} for c in display.columns],
        data=display.to_dict("records"),
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_cell={
            "fontFamily": "Inter, system-ui, sans-serif",
            "fontSize":   "13px",
            "padding":    "8px 14px",
            "textAlign":  "left",
            "border":     f"1px solid {COLOURS['border']}",
        },
        style_header={
            "backgroundColor": COLOURS["secondary"],
            "color":           "#FFFFFF",
            "fontWeight":      "600",
            "border":          f"1px solid {COLOURS['secondary']}",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"},  "backgroundColor": "#F1F5F9"},
            {
                "if": {"filter_query": '{p < 0.05?} = "Yes"'},
                "backgroundColor": "#ECFDF5",
                "color":           "#065F46",
                "fontWeight":      "600",
            },
        ],
    )


sig_pops = stats_df[stats_df["significant"] == "Yes"]["population"].map(POP_LABELS).tolist()
sig_text = (
    f"Significant populations (p < 0.05): **{', '.join(sig_pops)}**"
    if sig_pops
    else "No populations reached statistical significance (p < 0.05)."
)

tab2_layout = html.Div([
    html.Div([
        html.H3("Responder vs Non-responder Comparison", style={"margin": "0 0 4px", "color": COLOURS["text"]}),
        html.P(
            "Melanoma patients receiving miraclib — PBMC samples only. "
            "Mann-Whitney U test (two-sided, α = 0.05).",
            style={"color": COLOURS["muted"], "margin": 0, "fontSize": "14px"},
        ),
    ], style=CARD_STYLE),

    html.Div([dcc.Graph(figure=build_boxplot(), config={"displayModeBar": True})], style=CARD_STYLE),

    html.Div([
        html.H4("Statistical Results", style={"margin": "0 0 12px", "color": COLOURS["text"]}),
        html.Div(
            dcc.Markdown(sig_text),
            style={"marginBottom": "14px", "padding": "10px 16px",
                   "background": "#EFF6FF", "borderRadius": "6px",
                   "border": f"1px solid {COLOURS['primary']}",
                   "fontSize": "14px", "color": COLOURS["text"]},
        ),
        build_stats_table(),
        html.P(
            "Rows highlighted in green indicate statistically significant differences "
            "(p < 0.05). The Mann-Whitney U test is used as it does not assume normality.",
            style={"color": COLOURS["muted"], "fontSize": "12px", "marginTop": "10px"},
        ),
    ], style=CARD_STYLE),
], style={"padding": "8px"})


# Tab 3 — Baseline Subset (Part 4)
def kpi_card(label: str, value: str, colour: str = COLOURS["primary"]) -> html.Div:
    return html.Div([
        html.Div(label, style={"fontSize": "12px", "color": COLOURS["muted"], "fontWeight": "600", "textTransform": "uppercase", "letterSpacing": "0.05em"}),
        html.Div(value, style={"fontSize": "28px", "fontWeight": "700", "color": colour, "marginTop": "4px"}),
    ], style={**CARD_STYLE, "flex": "1", "minWidth": "140px", "textAlign": "center"})


def mini_bar(df: pd.DataFrame, x_col: str, y_col: str, colour: str, title: str) -> dcc.Graph:
    fig = go.Figure(go.Bar(
        x=df[x_col].astype(str),
        y=df[y_col],
        marker_color=colour,
        text=df[y_col],
        textposition="outside",
    ))
    fig.update_layout(
        title={"text": title, "x": 0.5, "xanchor": "center", "font": {"size": 13}},
        paper_bgcolor=COLOURS["bg"],
        plot_bgcolor=COLOURS["bg"],
        margin={"t": 50, "b": 40, "l": 30, "r": 20},
        height=240,
        font={"family": "Inter, system-ui, sans-serif", "size": 12},
        yaxis={"gridcolor": COLOURS["border"]},
        showlegend=False,
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


samples_df  = baseline["samples_df"]
by_project  = baseline["by_project"]
by_response = baseline["by_response"]
by_sex      = baseline["by_sex"]
n_subjects  = samples_df["subject"].nunique()

tab3_layout = html.Div([
    html.Div([
        html.H3("Baseline Cohort — Melanoma / PBMC / Miraclib", style={"margin": "0 0 4px", "color": COLOURS["text"]}),
        html.P(
            "Melanoma patients treated with miraclib, PBMC sample type, time_from_treatment_start = 0.",
            style={"color": COLOURS["muted"], "margin": 0, "fontSize": "14px"},
        ),
    ], style=CARD_STYLE),

    # KPI row
    html.Div([
        kpi_card("Total Samples",  str(len(samples_df)),      COLOURS["primary"]),
        kpi_card("Unique Subjects", str(n_subjects),           COLOURS["secondary"]),
        kpi_card("Projects",        str(samples_df["project"].nunique()), COLOURS["accent"]),
    ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap", "marginBottom": "16px"}),

    # Charts row
    html.Div([
        html.Div(mini_bar(by_project,  "project",  "sample_count",  COLOURS["primary"],   "Samples per Project"),  style={**CARD_STYLE, "flex": "1", "minWidth": "200px"}),
        html.Div(mini_bar(by_response, "response", "subject_count", COLOURS["secondary"],  "Subjects by Response"), style={**CARD_STYLE, "flex": "1", "minWidth": "200px"}),
        html.Div(mini_bar(by_sex,      "sex",      "subject_count", COLOURS["accent"],     "Subjects by Sex"),      style={**CARD_STYLE, "flex": "1", "minWidth": "200px"}),
    ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),

    # Detail tables
    html.Div([
        html.H4("Breakdown Tables", style={"margin": "0 0 12px", "color": COLOURS["text"]}),
        html.Div([
            html.Div([
                html.H5("Samples per Project", style={"margin": "0 0 8px", "color": COLOURS["muted"], "fontSize": "13px"}),
                make_table(by_project.rename(columns={"project": "Project", "sample_count": "Samples"}), "proj-table", page_size=10),
            ], style={"flex": "1", "minWidth": "180px"}),
            html.Div([
                html.H5("Subjects by Response", style={"margin": "0 0 8px", "color": COLOURS["muted"], "fontSize": "13px"}),
                make_table(by_response.rename(columns={"response": "Response", "subject_count": "Subjects"}), "resp-table", page_size=10),
            ], style={"flex": "1", "minWidth": "180px"}),
            html.Div([
                html.H5("Subjects by Sex", style={"margin": "0 0 8px", "color": COLOURS["muted"], "fontSize": "13px"}),
                make_table(by_sex.rename(columns={"sex": "Sex", "subject_count": "Subjects"}), "sex-table", page_size=10),
            ], style={"flex": "1", "minWidth": "180px"}),
        ], style={"display": "flex", "gap": "24px", "flexWrap": "wrap"}),
    ], style=CARD_STYLE),

    # Raw sample table
    html.Div([
        html.H4("Sample Detail", style={"margin": "0 0 12px", "color": COLOURS["text"]}),
        make_table(
            samples_df[["sample", "subject", "project", "sex", "response", "treatment",
                         "sample_type", "time_from_treatment_start",
                         "b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]],
            "baseline-table",
        ),
    ], style=CARD_STYLE),
], style={"padding": "8px"})


# App layout
app = dash.Dash(
    __name__,
    title="Loblaw Bio — Clinical Trial Dashboard",
    suppress_callback_exceptions=True,
)

app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.H1(
                "Loblaw Bio — Immune Cell Population Dashboard",
                style={"margin": 0, "fontSize": "20px", "fontWeight": "700", "color": "#FFFFFF"},
            ),
            html.P(
                "miraclib clinical trial · cell-count analysis",
                style={"margin": "2px 0 0", "fontSize": "13px", "color": "rgba(255,255,255,0.75)"},
            ),
        ]),
    ], style={
        "background":    f"linear-gradient(135deg, {COLOURS['primary']}, {COLOURS['secondary']})",
        "padding":       "18px 28px",
        "marginBottom":  "0",
    }),

    # Tabs
    dcc.Tabs(
        id="main-tabs",
        value="tab-overview",
        children=[
            dcc.Tab(label="Data Overview",      value="tab-overview",   style={"fontWeight": "600"}),
            dcc.Tab(label="Responder Analysis", value="tab-responder",  style={"fontWeight": "600"}),
            dcc.Tab(label="Baseline Subset",    value="tab-baseline",   style={"fontWeight": "600"}),
        ],
        colors={"border": COLOURS["border"], "primary": COLOURS["primary"], "background": COLOURS["bg"]},
        style={"fontFamily": "Inter, system-ui, sans-serif"},
    ),

    html.Div(id="tab-content", style={"maxWidth": "1400px", "margin": "0 auto", "padding": "16px 24px"}),

], style={"fontFamily": "Inter, system-ui, sans-serif", "background": COLOURS["bg"], "minHeight": "100vh"})


@callback(Output("tab-content", "children"), Input("main-tabs", "value"))
def render_tab(tab):
    if tab == "tab-overview":
        return tab1_layout
    if tab == "tab-responder":
        return tab2_layout
    return tab3_layout



if __name__ == "__main__":
    print("Dashboard running at  http://127.0.0.1:8050")
    app.run(debug=False)
