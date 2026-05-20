import sqlite3

import pandas as pd
from scipy import stats


POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]


# Part 2 — Relative frequency table

def get_frequency_table(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Returns one row per (sample × population) with columns:
    sample, total_count, population, count, percentage
    """
    query = """
        SELECT
            s.sample_id   AS sample,
            cc.b_cell,
            cc.cd8_t_cell,
            cc.cd4_t_cell,
            cc.nk_cell,
            cc.monocyte
        FROM samples s
        JOIN cell_counts cc ON cc.sample_id = s.sample_id
    """
    df = pd.read_sql_query(query, conn)

    df["total_count"] = df[POPULATIONS].sum(axis=1)

    rows = []
    for _, row in df.iterrows():
        for pop in POPULATIONS:
            rows.append({
                "sample":       row["sample"],
                "total_count":  int(row["total_count"]),
                "population":   pop,
                "count":        int(row[pop]),
                "percentage":   round(row[pop] / row["total_count"] * 100, 4),
            })

    return pd.DataFrame(rows)


# Part 3 — Statistical comparison: responders vs non-responders

def get_responder_comparison(conn: sqlite3.Connection) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Filters to: melanoma, miraclib, PBMC samples only.

    Returns:
      freq_df  — frequency table for this subset (used for boxplot)
      stats_df — per-population Mann-Whitney U results (U, p-value, significance)
    """
    query = """
        SELECT
            s.sample_id   AS sample,
            sub.response,
            cc.b_cell,
            cc.cd8_t_cell,
            cc.cd4_t_cell,
            cc.nk_cell,
            cc.monocyte
        FROM samples s
        JOIN subjects sub ON sub.subject_id = s.subject_id
        JOIN cell_counts cc ON cc.sample_id = s.sample_id
        WHERE sub.condition  = 'melanoma'
          AND sub.treatment  = 'miraclib'
          AND s.sample_type  = 'PBMC'
          AND sub.response   IN ('yes', 'no')
    """
    df = pd.read_sql_query(query, conn)
    df["total_count"] = df[POPULATIONS].sum(axis=1)

    # Build long-form frequency table
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

    # Mann-Whitney U test per population
    stat_rows = []
    for pop in POPULATIONS:
        resp   = freq_df.loc[(freq_df["population"] == pop) & (freq_df["response"] == "yes"), "percentage"]
        nonrsp = freq_df.loc[(freq_df["population"] == pop) & (freq_df["response"] == "no"),  "percentage"]

        u_stat, p_val = stats.mannwhitneyu(resp, nonrsp, alternative="two-sided")

        stat_rows.append({
            "population":      pop,
            "n_responders":    len(resp),
            "n_non_responders": len(nonrsp),
            "median_resp":     round(resp.median(), 2),
            "median_nonresp":  round(nonrsp.median(), 2),
            "U_statistic":     round(u_stat, 2),
            "p_value":         round(p_val, 6),
            "significant":     "Yes" if p_val < 0.05 else "No",
        })

    stats_df = pd.DataFrame(stat_rows).sort_values("p_value")
    return freq_df, stats_df


# Part 4 — Baseline melanoma PBMC subset (miraclib, time = 0)

def get_baseline_subset(conn: sqlite3.Connection) -> dict:
    """
    Returns a dict with:
      samples_df       — full sample rows for the filtered set
      by_project       — sample counts per project
      by_response      — subject counts by response status
      by_sex           — subject counts by sex
    """
    query = """
        SELECT
            s.sample_id                 AS sample,
            sub.subject_id              AS subject,
            sub.project,
            sub.condition,
            sub.sex,
            sub.treatment,
            sub.response,
            s.sample_type,
            s.time_from_treatment_start,
            cc.b_cell,
            cc.cd8_t_cell,
            cc.cd4_t_cell,
            cc.nk_cell,
            cc.monocyte
        FROM samples s
        JOIN subjects sub ON sub.subject_id = s.subject_id
        JOIN cell_counts cc ON cc.sample_id = s.sample_id
        WHERE sub.condition               = 'melanoma'
          AND s.sample_type               = 'PBMC'
          AND s.time_from_treatment_start = 0
          AND sub.treatment               = 'miraclib'
    """
    df = pd.read_sql_query(query, conn)

    by_project  = df.groupby("project")["sample"].count().reset_index()
    by_project.columns = ["project", "sample_count"]

    # Per-subject (deduplicate — each subject appears once at baseline)
    subjects_df = df.drop_duplicates("subject")
    by_response = subjects_df["response"].value_counts().reset_index()
    by_response.columns = ["response", "subject_count"]

    by_sex = subjects_df["sex"].value_counts().reset_index()
    by_sex.columns = ["sex", "subject_count"]

    return {
        "samples_df":   df,
        "by_project":   by_project,
        "by_response":  by_response,
        "by_sex":       by_sex,
    }
