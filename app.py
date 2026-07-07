"""quant-bot 網頁介面（Streamlit）。

啟動：  ./.venv/bin/streamlit run app.py
"""
from __future__ import annotations
import pandas as pd
import streamlit as st

from data.finmind import load
from strategies import REGISTRY
from backtest.engine import run_backtest, run_backtest_risk
from backtest.metrics import compute
from sweep import combos
from walkforward import walk_forward
from run import load_env

load_env()
st.set_page_config(page_title="quant-bot 回測", layout="wide")


@st.cache_data(show_spinner="載入 FinMind 資料中...")
def cached_load(ticker: str, start: str, end: str | None):
    return load(ticker, start, end)


def param_widgets(StratCls, key: str) -> dict:
    grid = getattr(StratCls, "PARAM_GRID", {})
    if not grid:
        return {}
    kwargs = {}
    cols = st.columns(len(grid))
    for (name, vals), col in zip(grid.items(), cols):
        kwargs[name] = col.selectbox(name, vals, index=len(vals) // 2, key=f"{key}_{name}")
    return kwargs


def show_metrics(m: dict):
    c = st.columns(5)
    c[0].metric("總報酬", f"{m['total_return']*100:.1f}%", f"買進持有 {m['buy_hold_return']*100:.1f}%")
    c[1].metric("年化 CAGR", f"{m['cagr']*100:.1f}%")
    c[2].metric("Sharpe", f"{m['sharpe']:.2f}")
    c[3].metric("最大回撤", f"{m['max_drawdown']*100:.1f}%")
    c[4].metric("勝率", f"{m['win_rate']*100:.0f}%", f"{m['num_trades']} 筆")


def equity_chart(bt: pd.DataFrame):
    st.line_chart(pd.DataFrame({"策略": bt["equity"], "買進持有": bt["benchmark"]}))
    dd = bt["equity"] / bt["equity"].cummax() - 1
    st.area_chart(dd.rename("回撤"), color="#e11d48")


# ── 側邊欄 ──
st.sidebar.title("quant-bot")
ticker = st.sidebar.text_input("股票代號", "2330")
strategy = st.sidebar.selectbox("策略", list(REGISTRY))
start = st.sidebar.text_input("起始日", "2021-01-01")
end = st.sidebar.text_input("結束日（空=最新）", "") or None
st.sidebar.markdown("---")
use_risk = st.sidebar.checkbox("啟用停損停利 / 部位控管")
stop = st.sidebar.number_input("停損 %", 0.0, 0.5, 0.08, 0.01) if use_risk else None
take = st.sidebar.number_input("停利 %（0=不設）", 0.0, 1.0, 0.20, 0.01) if use_risk else None
risk = st.sidebar.number_input("每筆風險預算（0=滿倉）", 0.0, 0.2, 0.0, 0.005) if use_risk else None
if take == 0:
    take = None
if risk == 0:
    risk = None

StratCls = REGISTRY[strategy]


def do_bt(d, p):
    if use_risk:
        return run_backtest_risk(d, p, stop_loss=stop, take_profit=take, risk_per_trade=risk)
    return run_backtest(d, p)


tab_bt, tab_sweep, tab_wf, tab_pf = st.tabs(["回測", "參數掃描", "Walk-forward", "多標的組合"])

with tab_bt:
    st.subheader(f"{strategy} @ {ticker}")
    kwargs = param_widgets(StratCls, "bt")
    try:
        df = cached_load(ticker, start, end)
        pos = StratCls(**kwargs).positions(df)
        bt = do_bt(df, pos)
        st.caption(f"{df.index[0].date()} ~ {df.index[-1].date()}｜{len(df)} 交易日")
        show_metrics(compute(bt))
        equity_chart(bt)
    except Exception as e:
        st.error(str(e))

with tab_sweep:
    st.subheader("參數掃描（訓練內選參、測試外驗證）")
    split = st.slider("樣本內比例", 0.3, 0.8, 0.6, 0.05, key="sweep_split")
    if st.button("執行掃描"):
        try:
            df = cached_load(ticker, start, end)
            k = int(len(df) * split)
            df_in, df_out = df.iloc[:k], df.iloc[k:]
            rows = []
            for params in combos(StratCls):
                mi = compute(run_backtest(df_in, StratCls(**params).positions(df_in)))
                mo = compute(run_backtest(df_out, StratCls(**params).positions(df_out)))
                rows.append({
                    "參數": ", ".join(f"{k2}={v}" for k2, v in params.items()),
                    "訓練Sharpe": round(mi["sharpe"], 2), "訓練報酬%": round(mi["total_return"] * 100, 1),
                    "測試Sharpe": round(mo["sharpe"], 2), "測試報酬%": round(mo["total_return"] * 100, 1),
                })
            out = pd.DataFrame(rows).sort_values("訓練Sharpe", ascending=False)
            st.dataframe(out, use_container_width=True, hide_index=True)
            st.caption("只用訓練 Sharpe 排名選參；看『測試』欄是否也撐得住＝是否過度擬合。")
        except Exception as e:
            st.error(str(e))

with tab_wf:
    st.subheader("Walk-forward 滾動最佳化（最接近實戰）")
    c1, c2 = st.columns(2)
    train = c1.number_input("訓練窗（日）", 60, 756, 252, 21)
    test = c2.number_input("測試窗（日）", 20, 252, 63, 21)
    if st.button("執行 Walk-forward"):
        try:
            df = cached_load(ticker, start, end)
            if len(df) < train + test + 10:
                st.warning("資料太短，請拉長起始日或縮小訓練/測試窗")
            else:
                bt, picks = walk_forward(df, StratCls, int(train), int(test))
                st.caption(f"滾動樣本外 {bt.index[0].date()} ~ {bt.index[-1].date()}｜{len(picks)} 段")
                show_metrics(compute(bt))
                equity_chart(bt)
                st.dataframe(
                    pd.DataFrame([{"換參日": str(d), "參數": ", ".join(f"{k2}={v}" for k2, v in p.items())} for d, p in picks]),
                    use_container_width=True, hide_index=True,
                )
        except Exception as e:
            st.error(str(e))

with tab_pf:
    st.subheader("多標的等權組合")
    tickers = st.text_input("股票代號（逗號分隔）", "2330,2454,3711,3661")
    if st.button("執行組合回測"):
        try:
            tlist = [t.strip() for t in tickers.split(",") if t.strip()]
            cols = {"ret": [], "gross": [], "held": [], "benchmark_ret": []}
            used = []
            for t in tlist:
                try:
                    d = cached_load(t, start, end)
                    b = do_bt(d, StratCls().positions(d))
                    for cc in cols:
                        cols[cc].append(b[cc].rename(t))
                    used.append(t)
                except Exception as e:
                    st.warning(f"略過 {t}：{e}")
            if used:
                ret = pd.concat(cols["ret"], axis=1).fillna(0.0).mean(axis=1)
                gross = pd.concat(cols["gross"], axis=1).fillna(0.0).mean(axis=1)
                held = pd.concat(cols["held"], axis=1).fillna(0.0).mean(axis=1)
                bret = pd.concat(cols["benchmark_ret"], axis=1).fillna(0.0).mean(axis=1)
                port = pd.DataFrame({"ret": ret, "gross": gross, "held": held,
                                     "equity": (1 + ret).cumprod(), "benchmark": (1 + bret).cumprod()})
                st.caption(f"{len(used)} 檔等權：{', '.join(used)}")
                show_metrics(compute(port))
                equity_chart(port)
        except Exception as e:
            st.error(str(e))
