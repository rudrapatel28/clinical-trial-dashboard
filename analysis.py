import sqlite3
import os
import pandas as pd
from scipy import stats

POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]
DB_PATH = os.path.join(os.path.dirname(__file__), "cell_trial.db")


# --- Part 2: Frequency Table ---

def get_frequency_table(conn):
    query = """
        SELECT s.sample_id AS sample, cc.b_cell, cc.cd8_t_cell, cc.cd4_t_cell, cc.nk_cell, cc.monocyte
        FROM samples s
        JOIN cell_counts cc ON cc.sample_id = s.sample_id
    """
    df = pd.read_sql_query(query, conn)
    df["total_count"] = df[POPULATIONS].sum(axis=1)
    rows = []
    for _, row in df.iterrows():
        for pop in POPULATIONS:
            rows.append({
                "sample":      row["sample"],
                "total_count": int(row["total_count"]),
                "population":  pop,
                "count":       int(row[pop]),
                "percentage":  round(row[pop] / row["total_count"] * 100, 4),
            })
    return pd.DataFrame(rows)


# --- Part 3: Responder Comparison ---

def get_responder_comparison(conn):
    query = """
        SELECT s.sample_id AS sample, sub.response,
               cc.b_cell, cc.cd8_t_cell, cc.cd4_t_cell, cc.nk_cell, cc.monocyte
        FROM samples s
        JOIN subjects sub ON sub.subject_id = s.subject_id
        JOIN cell_counts cc ON cc.sample_id = s.sample_id
        WHERE sub.condition = 'melanoma'
          AND sub.treatment = 'miraclib'
          AND s.sample_type = 'PBMC'
          AND sub.response IN ('yes', 'no')
    """
    df = pd.read_sql_query(query, conn)
    df["total_count"] = df[POPULATIONS].sum(axis=1)
    rows = []
    for _, row in df.iterrows():
        for pop in POPULATIONS:
            rows.append({
                "sample":     row["sample"],
                "response":   row["response"],
                "population": pop,
                "percentage": row[pop] / row["total_count"] * 100,
            })
    freq_df = pd.DataFrame(rows)

    stat_rows = []
    for pop in POPULATIONS:
        resp   = freq_df.loc[(freq_df["population"] == pop) & (freq_df["response"] == "yes"), "percentage"]
        nonrsp = freq_df.loc[(freq_df["population"] == pop) & (freq_df["response"] == "no"),  "percentage"]
        u_stat, p_val = stats.mannwhitneyu(resp, nonrsp, alternative="two-sided")
        stat_rows.append({
            "population":       pop,
            "n_responders":     len(resp),
            "n_non_responders": len(nonrsp),
            "median_resp":      round(resp.median(), 2),
            "median_nonresp":   round(nonrsp.median(), 2),
            "U_statistic":      round(u_stat, 2),
            "p_value":          round(p_val, 6),
            "significant":      "Yes" if p_val < 0.05 else "No",
        })
    stats_df = pd.DataFrame(stat_rows).sort_values("p_value")
    return freq_df, stats_df


# --- Part 4: Baseline Subset ---

def get_baseline_subset(conn):
    query = """
        SELECT s.sample_id AS sample, sub.subject_id AS subject, sub.project,
               sub.condition, sub.sex, sub.treatment, sub.response,
               s.sample_type, s.time_from_treatment_start,
               cc.b_cell, cc.cd8_t_cell, cc.cd4_t_cell, cc.nk_cell, cc.monocyte
        FROM samples s
        JOIN subjects sub ON sub.subject_id = s.subject_id
        JOIN cell_counts cc ON cc.sample_id = s.sample_id
        WHERE sub.condition = 'melanoma'
          AND s.sample_type = 'PBMC'
          AND s.time_from_treatment_start = 0
          AND sub.treatment = 'miraclib'
    """
    df = pd.read_sql_query(query, conn)
    by_project  = df.groupby("project")["sample"].count().reset_index()
    by_project.columns = ["project", "sample_count"]
    subjects_df = df.drop_duplicates("subject")
    by_response = subjects_df["response"].value_counts().reset_index()
    by_response.columns = ["response", "subject_count"]
    by_sex = subjects_df["sex"].value_counts().reset_index()
    by_sex.columns = ["sex", "subject_count"]
    avg_bcell = round(
        df[(df["sex"] == "M") & (df["response"] == "yes")]["b_cell"].mean(), 2
    )
    return {
        "samples_df":  df,
        "by_project":  by_project,
        "by_response": by_response,
        "by_sex":      by_sex,
        "avg_bcell_male_responders": avg_bcell,
    }


# --- Pipeline runner ---

if __name__ == "__main__":
    import plotly.express as px

    os.makedirs("outputs", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    # Part 2
    print("Running Part 2: Frequency Table...")
    freq_df = get_frequency_table(conn)
    freq_df.to_csv("outputs/frequency_table.csv", index=False)
    print(f"  Saved outputs/frequency_table.csv ({len(freq_df):,} rows)")

    # Part 3
    print("Running Part 3: Responder Comparison...")
    resp_freq_df, stats_df = get_responder_comparison(conn)
    stats_df.to_csv("outputs/stats_results.csv", index=False)
    print("  Saved outputs/stats_results.csv")
    print(stats_df.to_string(index=False))

    fig = px.box(
        resp_freq_df,
        x="population", y="percentage", color="response",
        title="Cell Population Frequencies: Responders vs Non-responders (Melanoma, miraclib, PBMC)",
        labels={"population": "Cell Population", "percentage": "Relative Frequency (%)", "response": "Response"},
        color_discrete_map={"yes": "#10B981", "no": "#EF4444"},
    )
    fig.write_image("outputs/boxplot.png")
    print("  Saved outputs/boxplot.png")

    # Part 4
    print("Running Part 4: Baseline Subset...")
    baseline = get_baseline_subset(conn)
    baseline["by_project"].to_csv("outputs/baseline_by_project.csv", index=False)
    baseline["by_response"].to_csv("outputs/baseline_by_response.csv", index=False)
    baseline["by_sex"].to_csv("outputs/baseline_by_sex.csv", index=False)
    print("  Saved outputs/baseline_by_project.csv")
    print("  Saved outputs/baseline_by_response.csv")
    print("  Saved outputs/baseline_by_sex.csv")
    print(f"  Avg B cells (melanoma male responders, time=0): {baseline['avg_bcell_male_responders']}")

    conn.close()
    print("\nPipeline complete.")