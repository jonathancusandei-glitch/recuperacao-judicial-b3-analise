# -*- coding: utf-8 -*-
"""Análise Econômico-Financeira Longitudinal de Companhias da B3 em Recuperação Judicial (2022–2025)."""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "base_consolidada_rj_b3.csv")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)


def parse_pt_num(val):
    if pd.isna(val):
        return np.nan
    s = str(val).strip().replace("%", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return np.nan


def load_data():
    df = pd.read_csv(CSV_PATH, sep=";", encoding="utf-8")
    for col in ["2022", "2023", "2024", "2025"]:
        df[col] = df[col].apply(parse_pt_num)
    return df


def _pick_metric(idx_map, prefix: str, yr: str):
    mask = idx_map.index.str.startswith(prefix)
    vals = idx_map.loc[mask, yr].values
    return float(vals[0]) if len(vals) else np.nan


def detect_false_positive_roe(df):
    rows = []
    for ticker, grp in df.groupby("Ticker"):
        idx_map = grp.set_index("Conta_ou_Indicador")
        for yr in ["2022", "2023", "2024", "2025"]:
            ll = _pick_metric(idx_map, "Lucro / Prejuízo Líquido", yr)
            pl = _pick_metric(idx_map, "Patrimônio Líquido", yr)
            ebitda = _pick_metric(idx_map, "Margem EBITDA", yr)
            lc = _pick_metric(idx_map, "Liquidez Corrente", yr)
            eg = _pick_metric(idx_map, "Endividamento Geral", yr)
            roe = _pick_metric(idx_map, "ROE", yr)
            if not (np.isnan(ll) or np.isnan(pl) or np.isnan(roe)):
                false_pos = bool(ll < 0 and pl < 0 and roe > 0)
                rows.append({
                    "Ticker": ticker,
                    "Ano": int(yr),
                    "Lucro_Liquido_Mi": ll,
                    "Patrimonio_Liquido_Mi": pl,
                    "Liquidez_Corrente": lc,
                    "Endividamento_Geral_Pct": eg,
                    "ROE_Nominal_Pct": roe,
                    "Margem_EBITDA_Pct": ebitda,
                    "ROE_Falso_Positivo": false_pos,
                })
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(OUT_DIR, "resumo_indicadores_validados.csv"), index=False, encoding="utf-8")
    return res


def generate_charts(summary):
    plt.style.use("seaborn-v0_8-whitegrid")
    tickers = ["LIGT3", "AMER3", "ATMP3", "RSID3", "PMAM3", "NEXP3"]
    sub_2025 = summary[summary["Ano"] == 2025].set_index("Ticker").reindex(tickers)

    # 1. Liquidez Corrente vs Endividamento Geral (2025)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    colors_lc = ["#10b981" if v >= 1.0 else "#ef4444" for v in sub_2025["Liquidez_Corrente"]]
    axes[0].bar(sub_2025.index, sub_2025["Liquidez_Corrente"], color=colors_lc)
    axes[0].axhline(1.0, color="#1e293b", linestyle="--", linewidth=1.2, label="Equilíbrio (1,00)")
    axes[0].set_title("Liquidez Corrente (2025)", fontweight="bold")
    axes[0].set_ylabel("AC / PC")
    axes[0].legend()

    colors_eg = ["#2563eb" if v < 100 else "#dc2626" for v in sub_2025["Endividamento_Geral_Pct"]]
    axes[1].bar(sub_2025.index, sub_2025["Endividamento_Geral_Pct"], color=colors_eg)
    axes[1].axhline(100, color="#1e293b", linestyle="--", linewidth=1.2, label="Passivo a Descoberto (100%)")
    axes[1].set_title("Endividamento Geral — PT / AT % (2025)", fontweight="bold")
    axes[1].set_ylabel("%")
    axes[1].legend()
    fig.suptitle("Solvência de Companhias da B3 em Recuperação Judicial (2025)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "liquidez_vs_endividamento.png"), dpi=150)
    plt.close(fig)

    # 2. Distorção ROE vs Margem EBITDA (Falsos Positivos)
    fig, ax = plt.subplots(figsize=(10.5, 5))
    x = np.arange(len(tickers))
    w = 0.36
    roe_vals = np.clip(sub_2025["ROE_Nominal_Pct"].values, -150, 150)
    eb_vals = np.clip(sub_2025["Margem_EBITDA_Pct"].values, -150, 150)
    ax.bar(x - w/2, roe_vals, w, label="ROE Nominal (Distorcido quando PL < 0 e LL < 0)", color="#f59e0b")
    ax.bar(x + w/2, eb_vals, w, label="Margem EBITDA Operacional (%)", color="#2563eb")
    ax.axhline(0, color="#0f172a", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(tickers, fontweight="bold")
    ax.set_ylabel("% (recortado em ±150% para legibilidade)")
    ax.set_title("Armadilha Algébrica do ROE vs. Geração Operacional Real (2025)", fontweight="bold")
    ax.legend()
    plt.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "roe_falso_positivo_vs_ebitda.png"), dpi=150)
    plt.close(fig)

    # 3. Evolução da Liquidez Corrente (2022-2025)
    fig, ax = plt.subplots(figsize=(10.5, 5))
    for t in tickers:
        s = summary[summary["Ticker"] == t].sort_values("Ano")
        ax.plot(s["Ano"], s["Liquidez_Corrente"], marker="o", linewidth=2.2, label=t)
    ax.axhline(1.0, color="#64748b", linestyle="--", linewidth=1.2)
    ax.set_xticks([2022, 2023, 2024, 2025])
    ax.set_title("Trajetória da Liquidez Corrente (2022–2025)", fontweight="bold")
    ax.set_ylabel("Liquidez Corrente (AC / PC)")
    ax.legend(ncol=3)
    plt.tight_layout()
    fig.savefig(os.path.join(ASSETS_DIR, "trajetoria_liquidez_b3.png"), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    df_raw = load_data()
    res = detect_false_positive_roe(df_raw)
    generate_charts(res)
    fp_cases = res[res["ROE_Falso_Positivo"]]
    print(f"Empresas-ano analisadas: {len(res)} | Falsos positivos no ROE detectados: {len(fp_cases)}")
    print(res[res["Ano"] == 2025].to_string(index=False))
