"""
Contas Pessoais SP — Análise de Fluxo de Caixa
Baseado no TrelloCashFlowAnalyzer (contas a pagar).

Diferencial: cards com label "Apartamento SP" têm valor dividido por 2
(conta compartilhada com a esposa).
"""

import re
import pytz
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ──────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────

BOARD_URL = "https://trello.com/b/CEyzMtRp/contas-sp"
SPLIT_LABEL = "Apartamento SP"   # label que aciona divisão por 2
BR_TZ = pytz.timezone("America/Sao_Paulo")

MONTHS_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

DAY_NAMES_PT = {
    "Monday": "Seg", "Tuesday": "Ter", "Wednesday": "Qua",
    "Thursday": "Qui", "Friday": "Sex", "Saturday": "Sáb", "Sunday": "Dom",
}


# ──────────────────────────────────────────────
# HELPERS DE FORMATAÇÃO
# ──────────────────────────────────────────────

def fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ──────────────────────────────────────────────
# CLASSE PRINCIPAL
# ──────────────────────────────────────────────

class ContasPessoaisAnalyzer:
    def __init__(self):
        self.base_url = "https://api.trello.com/1"
        self.api_key: Optional[str] = None
        self.token: Optional[str] = None

    # ── Credenciais ──────────────────────────────────────────────
    def load_credentials(self) -> bool:
        self.api_key = st.secrets.get("TRELLO_API_KEY")
        self.token = st.secrets.get("TRELLO_TOKEN")
        if not self.api_key or not self.token:
            st.error(
                "❌ Credenciais TRELLO_API_KEY ou TRELLO_TOKEN não encontradas "
                "nos Secrets do Streamlit."
            )
            return False
        return True

    # ── Extração de board ID ──────────────────────────────────────
    def extract_board_id(self, board_url: str) -> str:
        match = re.search(r"/b/([a-zA-Z0-9]+)/", board_url)
        if match:
            return match.group(1)
        raise ValueError(f"URL do board inválida: {board_url}")

    # ── Requests com cache de 10 min ──────────────────────────────
    @st.cache_data(ttl=600, show_spinner=False)
    def _fetch_lists(_self, board_id: str) -> List[Dict]:
        url = f"{_self.base_url}/boards/{board_id}/lists"
        params = {"key": _self.api_key, "token": _self.token}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    @st.cache_data(ttl=600, show_spinner=False)
    def _fetch_cards(_self, list_id: str) -> List[Dict]:
        """Busca cards com labels incluídos (fields=name,labels)."""
        url = f"{_self.base_url}/lists/{list_id}/cards"
        params = {
            "key": _self.api_key,
            "token": _self.token,
            "fields": "name,labels",   # ← traz labels para detectar split
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()

    # ── Board / listas ────────────────────────────────────────────
    def get_board_lists(self, board_url: str) -> List[Dict]:
        try:
            board_id = self.extract_board_id(board_url)
            return self._fetch_lists(board_id)
        except Exception as e:
            st.error(f"❌ Erro ao buscar listas do Trello: {e}")
            return []

    def identify_month_lists(
        self, lists: List[Dict], start_date: datetime, end_date: datetime
    ) -> List[str]:
        months_needed: set = set()
        current = start_date
        while current <= end_date:
            months_needed.add((MONTHS_PT[current.month], str(current.year)[2:]))
            current = (current.replace(day=1) + timedelta(days=32)).replace(day=1)

        list_ids = []
        for lst in lists:
            name = lst["name"].lower().strip()
            for month_name, year_short in months_needed:
                if re.search(rf"{month_name}\s*/\s*{year_short}", name):
                    list_ids.append(lst["id"])
                    break
        return list_ids

    def get_cards_from_lists(self, list_ids: List[str]) -> List[Dict]:
        all_cards: List[Dict] = []
        for list_id in list_ids:
            try:
                all_cards.extend(self._fetch_cards(list_id))
            except Exception:
                continue
        return all_cards

    # ── Parsing de cards ──────────────────────────────────────────
    @staticmethod
    def _card_has_split_label(card: Dict) -> bool:
        """Retorna True se o card tiver o label SPLIT_LABEL pelo nome."""
        labels = card.get("labels") or []
        return any(lbl.get("name", "") == SPLIT_LABEL for lbl in labels)

    def parse_card(
        self, card: Dict
    ) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Faz parse de um card completo (nome + labels).
        Retorna (registro_dict, None) ou (None, motivo_erro).
        """
        title = card["name"].strip()
        parts = [p.strip() for p in title.split("-", 2)]

        if len(parts) < 3:
            return None, "Formato inválido — esperado: DD/MM/AA - R$ valor - nome"

        # Data
        try:
            date_obj = datetime.strptime(parts[0], "%d/%m/%y")
        except ValueError:
            return None, f"Data inválida: '{parts[0]}' — use DD/MM/AA"

        # Valor
        value_str = (
            re.sub(r"[R$\s]", "", parts[1])
            .replace(".", "")
            .replace(",", ".")
        )
        if not value_str:
            return None, "Valor ausente ou ilegível"
        try:
            value = float(value_str)
        except ValueError:
            return None, f"Valor inválido: '{parts[1]}'"

        name = parts[2]
        is_split = self._card_has_split_label(card)

        # Aplica divisão por 2 se tiver o label
        valor_final = value / 2 if is_split else value

        return {
            "data": date_obj,
            "valor_original": value,
            "valor": valor_final,
            "nome": name,
            "apartamento_sp": is_split,
            "titulo_original": title,
        }, None

    def parse_all_cards(
        self, cards: List[Dict]
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Retorna (df_validos, df_invalidos)."""
        validos, invalidos = [], []

        for card in cards:
            registro, error = self.parse_card(card)
            if registro:
                validos.append(registro)
            else:
                invalidos.append({"titulo_original": card["name"], "motivo": error})

        df_validos = pd.DataFrame(validos)
        if not df_validos.empty:
            df_validos = df_validos.sort_values("data").reset_index(drop=True)

        return df_validos, pd.DataFrame(invalidos)

    # ── Cálculos ──────────────────────────────────────────────────
    def filter_by_range(
        self, df: pd.DataFrame, start: datetime, end: datetime
    ) -> pd.DataFrame:
        if df.empty:
            return df
        return df[(df["data"] >= start) & (df["data"] <= end)].copy()

    def calculate_monthly_expenses(
        self, df: pd.DataFrame, today: datetime
    ) -> float:
        if df.empty:
            return 0.0
        first = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return df[(df["data"] >= first) & (df["data"] <= today)]["valor"].sum()

    def calculate_daily_totals(
        self, df: pd.DataFrame, start: datetime, end: datetime
    ) -> pd.DataFrame:
        date_range = pd.date_range(start=start, end=end, freq="D")

        if not df.empty:
            daily = df.groupby("data")["valor"].sum().reset_index()
            daily.columns = ["data", "total_saidas"]
        else:
            daily = pd.DataFrame(columns=["data", "total_saidas"])

        result = pd.DataFrame({"data": date_range}).merge(daily, on="data", how="left")
        result["total_saidas"] = result["total_saidas"].fillna(0)
        result["saldo_acumulado"] = -result["total_saidas"].cumsum()
        result["data_formatada"] = result["data"].dt.strftime("%d/%m/%Y")
        result["dia_semana"] = result["data"].dt.day_name().map(DAY_NAMES_PT)
        return result

    # ── Gráficos ──────────────────────────────────────────────────
    def chart_monthly_comparison(
        self, df: pd.DataFrame, start: datetime, end: datetime
    ) -> go.Figure:
        """
        Uma barra por mês dentro do período selecionado.
        Meses sem dados aparecem como zero (barra vazia).
        """
        # Gera todos os meses do intervalo como rótulos
        months: List[str] = []
        totals: List[float] = []

        current = start.replace(day=1)
        while current <= end:
            label = f"{MONTHS_PT[current.month].capitalize()}/{str(current.year)[2:]}"
            months.append(label)

            if not df.empty:
                mask = (
                    (df["data"].dt.year == current.year) &
                    (df["data"].dt.month == current.month)
                )
                totals.append(df[mask]["valor"].sum())
            else:
                totals.append(0.0)

            # Avança um mês
            current = (current.replace(day=1) + timedelta(days=32)).replace(day=1)

        # Destaca o mês atual com cor diferente
        this_month = today.strftime(f"{MONTHS_PT[today.month].capitalize()}/{str(today.year)[2:]}")
        colors = ["#2A7A9B" if m != this_month else "#F59E0B" for m in months]

        fig = go.Figure(
            go.Bar(
                x=months,
                y=totals,
                marker_color=colors,
                text=[fmt_brl(v) if v > 0 else "" for v in totals],
                textposition="outside",
                width=0.55,
            )
        )

        fig.update_layout(
            title="Comparativo de Gastos por Mês (minha parte)",
            xaxis=dict(title="", showgrid=False),
            yaxis=dict(
                title="Total (R$)", tickprefix="R$ ",
                showgrid=True, gridcolor="#EBEBEB", nticks=6,
            ),
            height=460,
            plot_bgcolor="#FAFBFC",
            paper_bgcolor="#FFFFFF",
            margin=dict(t=60, b=40),
            showlegend=False,
            annotations=[
                dict(
                    x=0.5, y=1.08, xref="paper", yref="paper",
                    text="🟡 mês atual",
                    showarrow=False,
                    font=dict(size=12, color="#8B95A5"),
                )
            ],
        )
        return fig

    def chart_suppliers(self, df: pd.DataFrame) -> go.Figure:
        if df.empty:
            return go.Figure()

        supplier_totals = (
            df.groupby("nome")["valor"]
            .sum()
            .sort_values(ascending=True)
            .tail(12)
        )

        fig = go.Figure(
            go.Bar(
                x=supplier_totals.values,
                y=supplier_totals.index,
                orientation="h",
                marker=dict(
                    color=supplier_totals.values,
                    colorscale=[[0, "#C9E8F4"], [1, "#2A7A9B"]],
                ),
                text=[fmt_brl(v) for v in supplier_totals.values],
                textposition="outside",
            )
        )
        fig.update_layout(
            title="Gastos por Categoria / Fornecedor",
            xaxis=dict(
                title="Total (R$)", tickprefix="R$ ",
                showgrid=True, gridcolor="#F0F2F5",
            ),
            yaxis=dict(title=""),
            height=420,
            plot_bgcolor="#FAFBFC",
            paper_bgcolor="#FFFFFF",
            margin=dict(l=20, r=100, t=50, b=20),
        )
        return fig

    def chart_split_breakdown(self, df: pd.DataFrame) -> go.Figure:
        """Pizza: proporção dos gastos 'meus' vs 'Apartamento SP (minha metade)'."""
        if df.empty:
            return go.Figure()

        total_split = df[df["apartamento_sp"]]["valor"].sum()
        total_proprio = df[~df["apartamento_sp"]]["valor"].sum()

        fig = go.Figure(
            go.Pie(
                labels=["Gastos próprios", f"{SPLIT_LABEL} (minha metade)"],
                values=[total_proprio, total_split],
                hole=0.45,
                marker=dict(colors=["#2A7A9B", "#F59E0B"]),
                textinfo="label+percent+value",
                texttemplate="%{label}<br>%{percent} · R$ %{value:,.2f}",
            )
        )
        fig.update_layout(
            title=f"Composição dos Gastos — '{SPLIT_LABEL}' vs Demais",
            height=380,
            paper_bgcolor="#FFFFFF",
        )
        return fig


# ──────────────────────────────────────────────
# APP STREAMLIT
# ──────────────────────────────────────────────

st.set_page_config(page_title="Contas Pessoais SP", page_icon="🏠", layout="wide")
st.title("🏠 Contas Pessoais SP")
st.caption(
    f"Cards com label **{SPLIT_LABEL}** têm o valor dividido por 2 "
    "(conta compartilhada com a esposa)."
)

analyzer = ContasPessoaisAnalyzer()
if not analyzer.load_credentials():
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────
today = datetime.now(tz=BR_TZ).replace(
    hour=0, minute=0, second=0, microsecond=0, tzinfo=None
)

with st.sidebar:
    st.header("⚙️ Configurações")
    date_range = st.date_input(
        "Período de análise",
        value=(today.date(), today.replace(day=28).date()),
        min_value=(today - timedelta(days=730)).date(),
        max_value=(today + timedelta(days=90)).date(),
        help="Selecione o intervalo de datas para visualizar os gastos.",
    )
    st.caption(
        "💡 Cache renovado a cada 10 min. "
        "Para forçar atualização pressione **F5**."
    )
    exclusion_placeholder = st.empty()

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    start_date = datetime.combine(date_range[0], datetime.min.time())
    end_date = datetime.combine(date_range[1], datetime.min.time())
else:
    start_date = today
    end_date = today + timedelta(days=6)

# ── Busca de dados ────────────────────────────────────────────────
with st.spinner("Conectando ao Trello…"):
    lists = analyzer.get_board_lists(BOARD_URL)

if not lists:
    st.warning("Nenhuma lista encontrada no board.")
    st.stop()

list_ids = analyzer.identify_month_lists(lists, start_date, end_date)
cards = analyzer.get_cards_from_lists(list_ids)

if not cards:
    st.warning("Nenhum card encontrado nas listas do período.")
    st.stop()

df_all, df_invalidos = analyzer.parse_all_cards(cards)

# ── Filtro de exclusão de categorias (sidebar) ────────────────────
DEFAULT_EXCLUDED: List[str] = []
all_names = sorted(df_all["nome"].unique().tolist()) if not df_all.empty else []

with exclusion_placeholder.container():
    st.divider()
    st.markdown("**🚫 Excluir categorias**")
    excluded = st.multiselect(
        label="Categorias ignoradas nos cálculos",
        options=all_names,
        default=[n for n in DEFAULT_EXCLUDED if n in all_names],
        help="Cards com esses nomes não entram nos totais nem nos gráficos.",
    )

if excluded:
    df_all = df_all[~df_all["nome"].isin(excluded)].copy()

df_period = analyzer.filter_by_range(df_all, start_date, end_date)
monthly_expenses = analyzer.calculate_monthly_expenses(df_all, today)

# ── YoY ───────────────────────────────────────────────────────────
start_yoy = start_date.replace(year=start_date.year - 1)
end_yoy = end_date.replace(year=end_date.year - 1)
today_yoy = today.replace(year=today.year - 1)

list_ids_yoy = analyzer.identify_month_lists(lists, start_yoy, end_yoy)
cards_yoy = analyzer.get_cards_from_lists(list_ids_yoy)

if cards_yoy:
    df_all_yoy, _ = analyzer.parse_all_cards(cards_yoy)
    if excluded:
        df_all_yoy = df_all_yoy[~df_all_yoy["nome"].isin(excluded)].copy()
    monthly_expenses_yoy = analyzer.calculate_monthly_expenses(df_all_yoy, today_yoy)
    period_total_yoy = analyzer.filter_by_range(df_all_yoy, start_yoy, end_yoy)["valor"].sum()
else:
    monthly_expenses_yoy = None
    period_total_yoy = None


def yoy_delta(current: float, previous: Optional[float]) -> Tuple[Optional[str], Optional[float]]:
    if previous is None or previous == 0:
        return None, None
    pct = (current - previous) / previous * 100
    arrow = "▲" if pct > 0 else "▼"
    return f"{arrow} {abs(pct):.1f}% vs {today.year - 1}", pct


# ── KPIs ──────────────────────────────────────────────────────────
period_total = df_period["valor"].sum() if not df_period.empty else 0.0
biggest_expense = df_period["valor"].max() if not df_period.empty else 0.0
biggest_name = (
    df_period.loc[df_period["valor"].idxmax(), "nome"]
    if not df_period.empty else "—"
)

# KPI extra: quanto é "Apartamento SP" no período
split_total = (
    df_period[df_period["apartamento_sp"]]["valor"].sum()
    if not df_period.empty else 0.0
)

delta_month, _ = yoy_delta(monthly_expenses, monthly_expenses_yoy)
delta_period, _ = yoy_delta(period_total, period_total_yoy)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="📅 Gasto acumulado no mês (minha parte)",
        value=fmt_brl(monthly_expenses),
        delta=delta_month,
        delta_color="inverse",
        help=(
            f"Comparado ao mesmo período de {today.year - 1}: "
            f"{fmt_brl(monthly_expenses_yoy) if monthly_expenses_yoy else 'sem dados'}"
        ),
    )

with col2:
    st.metric(
        label="🗓️ Total no período selecionado",
        value=fmt_brl(period_total),
        delta=delta_period,
        delta_color="inverse",
        help=(
            f"Comparado ao mesmo período de {today.year - 1}: "
            f"{fmt_brl(period_total_yoy) if period_total_yoy else 'sem dados'}"
        ),
    )

with col3:
    st.metric(
        label=f"🏠 {SPLIT_LABEL} no período (minha metade)",
        value=fmt_brl(split_total),
        help="Soma dos valores já divididos por 2 para cards com esse label.",
    )

with col4:
    st.metric(
        "🔺 Maior gasto individual",
        fmt_brl(biggest_expense),
        help=f"Referente a: {biggest_name}",
    )

st.divider()

# ── Comparativo mensal ────────────────────────────────────────────
fig_monthly = analyzer.chart_monthly_comparison(df_all, start_date, end_date)
st.plotly_chart(fig_monthly, use_container_width=True)

# ── Gráfico de fornecedores ───────────────────────────────────────
if not df_period.empty:
    fig_suppliers = analyzer.chart_suppliers(df_period)
    st.plotly_chart(fig_suppliers, use_container_width=True)

# ── Pizza: composição split vs próprio ───────────────────────────
if not df_period.empty and df_period["apartamento_sp"].any():
    fig_split = analyzer.chart_split_breakdown(df_period)
    st.plotly_chart(fig_split, use_container_width=True)

st.divider()

# ── Tabela detalhada ──────────────────────────────────────────────
st.subheader("📋 Detalhamento dos Cards")

if not df_period.empty:
    df_display = df_period[["data", "valor_original", "valor", "nome", "apartamento_sp"]].copy()
    df_display["data"] = df_display["data"].dt.strftime("%d/%m/%Y")
    df_display["apartamento_sp"] = df_display["apartamento_sp"].map(
        {True: f"✅ {SPLIT_LABEL}", False: "—"}
    )
    df_display["valor_original"] = df_display["valor_original"].apply(
        lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    df_display["valor"] = df_display["valor"].apply(
        lambda v: f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    )
    df_display = df_display.rename(columns={
        "data": "Data",
        "valor_original": "Valor Original (R$)",
        "valor": "Minha Parte (R$)",
        "nome": "Descrição",
        "apartamento_sp": "Label",
    })
    st.dataframe(df_display, use_container_width=True, hide_index=True)
else:
    st.info("Nenhum card no período selecionado.")

# ── Cards inválidos ───────────────────────────────────────────────
if not df_invalidos.empty:
    with st.expander(
        f"⚠️ {len(df_invalidos)} card(s) com formato inválido — clique para ver"
    ):
        st.caption(
            "Estes cards foram ignorados pois não seguem o padrão esperado: "
            "`DD/MM/AA - R$ valor - descrição`"
        )
        st.dataframe(
            df_invalidos.rename(columns={
                "titulo_original": "Título no Trello",
                "motivo": "Motivo do Erro",
            }),
            use_container_width=True,
            hide_index=True,
        )
