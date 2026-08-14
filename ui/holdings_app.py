
import os
import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURATION
# ============================================================

HOLDINGS_FILE = "portfolio/holdings_raw.csv"

ASSET_TYPES = [
    "STOCK",
    "ETF",
    "CASH",
    "OTHER",
]


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Portfolio Holdings",
    page_icon="📊",
    layout="wide",
)


# ============================================================
# HELPERS
# ============================================================

def load_holdings():

    if not os.path.exists(HOLDINGS_FILE):
        return pd.DataFrame()

    try:

        df = pd.read_csv(HOLDINGS_FILE)

        if "Ticker" in df.columns:

            df["Ticker"] = (
                df["Ticker"]
                .astype(str)
                .str.strip()
                .str.upper()
            )

        return df

    except Exception as e:

        st.error(
            f"Unable to read holdings file: {e}"
        )

        return pd.DataFrame()


def save_holdings(df):

    try:

        directory = os.path.dirname(HOLDINGS_FILE)

        if directory:
            os.makedirs(
                directory,
                exist_ok=True
            )

        df.to_csv(
            HOLDINGS_FILE,
            index=False
        )

        return True

    except Exception as e:

        st.error(
            f"Unable to save holdings: {e}"
        )

        return False


def numeric_value(value):

    try:

        if pd.isna(value):
            return 0.0

        return float(value)

    except Exception:

        return 0.0


# ============================================================
# SESSION STATE
# ============================================================

if "holdings" not in st.session_state:

    st.session_state.holdings = load_holdings()


if "editing_ticker" not in st.session_state:

    st.session_state.editing_ticker = None


holdings = st.session_state.holdings


# ============================================================
# TITLE
# ============================================================

st.title("📊 Portfolio Holdings Manager")

st.caption(
    f"Managing: {HOLDINGS_FILE}"
)


# ============================================================
# SUMMARY
# ============================================================

if not holdings.empty:

    total_value = 0.0

    if "Market Value" in holdings.columns:

        total_value = (
            pd.to_numeric(
                holdings["Market Value"],
                errors="coerce"
            )
            .fillna(0)
            .sum()
        )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Holdings",
        len(holdings)
    )

    col2.metric(
        "Portfolio Value",
        f"£{total_value:,.2f}"
    )

    col3.metric(
        "File",
        "Connected"
    )

else:

    st.warning(
        "No holdings currently loaded."
    )


st.divider()


# ============================================================
# TOP-LEVEL NAVIGATION
# ============================================================

section = st.radio(
    "Portfolio Manager",
    [
        "View / Edit Holdings",
        "Add Holding",
        "Delete Holding",
    ],
    horizontal=True,
    key="main_section",
)


# ============================================================
# VIEW / EDIT HOLDINGS
# ============================================================

if section == "View / Edit Holdings":

    st.subheader("Current Holdings")

    if holdings.empty:

        st.info(
            "No holdings found."
        )

    else:

        st.caption(
            "Click Edit beside a holding to modify that position."
        )

        # ----------------------------------------------------
        # Table header
        # ----------------------------------------------------

        header = st.columns(
            [
                1.0,
                1.2,
                1.3,
                1.5,
                1.0,
                0.7,
            ]
        )

        header[0].markdown("**Ticker**")
        header[1].markdown("**Quantity**")
        header[2].markdown("**Market Value**")
        header[3].markdown("**Name**")
        header[4].markdown("**Asset Type**")
        header[5].markdown("**Action**")

        st.divider()

        # ----------------------------------------------------
        # Holdings
        # ----------------------------------------------------

        for row_index, row in holdings.iterrows():

            ticker = str(
                row.get(
                    "Ticker",
                    ""
                )
            )

            quantity = numeric_value(
                row.get(
                    "Quantity",
                    0
                )
            )

            market_value = numeric_value(
                row.get(
                    "Market Value",
                    0
                )
            )

            name = str(
                row.get(
                    "Name",
                    ""
                )
            )

            asset_type = str(
                row.get(
                    "Asset Type",
                    ""
                )
            )

            cols = st.columns(
                [
                    1.0,
                    1.2,
                    1.3,
                    1.5,
                    1.0,
                    0.7,
                ]
            )

            cols[0].write(ticker)

            cols[1].write(
                f"{quantity:.6f}"
            )

            cols[2].write(
                f"£{market_value:,.2f}"
            )

            cols[3].write(name)

            cols[4].write(asset_type)

            if cols[5].button(
                "✏️ Edit",
                key=f"edit_{ticker}_{row_index}",
                use_container_width=True,
            ):

                st.session_state.editing_ticker = ticker

                st.rerun()

            st.divider()

        # ----------------------------------------------------
        # EDIT FORM
        # ----------------------------------------------------

        editing_ticker = (
            st.session_state.editing_ticker
        )

        if editing_ticker:

            matching_rows = holdings.index[
                holdings["Ticker"] == editing_ticker
            ]

            if len(matching_rows) > 0:

                row_index = matching_rows[0]

                current = holdings.loc[
                    row_index
                ]

                st.subheader(
                    f"✏️ Edit {editing_ticker}"
                )

                st.info(
                    f"Editing holding: {editing_ticker}"
                )

                col1, col2 = st.columns(2)

                with col1:

                    edit_quantity = st.number_input(
                        "Quantity",
                        min_value=0.0,
                        value=numeric_value(
                            current.get(
                                "Quantity",
                                0
                            )
                        ),
                        step=0.001,
                        format="%.6f",
                        key=f"quantity_{editing_ticker}",
                    )

                    edit_market_value = st.number_input(
                        "Market Value",
                        min_value=0.0,
                        value=numeric_value(
                            current.get(
                                "Market Value",
                                0
                            )
                        ),
                        step=0.01,
                        key=f"market_value_{editing_ticker}",
                    )

                with col2:

                    edit_name = st.text_input(
                        "Name",
                        value=str(
                            current.get(
                                "Name",
                                ""
                            )
                        ),
                        key=f"name_{editing_ticker}",
                    )

                    current_asset_type = str(
                        current.get(
                            "Asset Type",
                            "STOCK"
                        )
                    ).upper()

                    if current_asset_type not in ASSET_TYPES:

                        current_asset_type = "STOCK"

                    edit_asset_type = st.selectbox(
                        "Asset Type",
                        ASSET_TYPES,
                        index=ASSET_TYPES.index(
                            current_asset_type
                        ),
                        key=f"asset_type_{editing_ticker}",
                    )

                st.divider()

                save_col, cancel_col = st.columns(2)

                with save_col:

                    if st.button(
                        "💾 Update Holding",
                        type="primary",
                        use_container_width=True,
                        key=f"update_{editing_ticker}",
                    ):

                        st.session_state.holdings.at[
                            row_index,
                            "Quantity"
                        ] = edit_quantity

                        st.session_state.holdings.at[
                            row_index,
                            "Market Value"
                        ] = edit_market_value

                        if "Name" in holdings.columns:

                            st.session_state.holdings.at[
                                row_index,
                                "Name"
                            ] = edit_name

                        if "Asset Type" in holdings.columns:

                            st.session_state.holdings.at[
                                row_index,
                                "Asset Type"
                            ] = edit_asset_type

                        if save_holdings(
                            st.session_state.holdings
                        ):

                            st.session_state.editing_ticker = None

                            st.success(
                                f"{editing_ticker} updated successfully."
                            )

                            st.rerun()

                with cancel_col:

                    if st.button(
                        "Cancel",
                        use_container_width=True,
                        key=f"cancel_{editing_ticker}",
                    ):

                        st.session_state.editing_ticker = None

                        st.rerun()

            else:

                st.session_state.editing_ticker = None


        # ----------------------------------------------------
        # RELOAD
        # ----------------------------------------------------

        st.divider()

        if st.button(
            "🔄 Reload CSV",
            use_container_width=True,
            key="reload_csv",
        ):

            st.session_state.holdings = load_holdings()

            st.session_state.editing_ticker = None

            st.rerun()


# ============================================================
# ADD HOLDING
# ============================================================

elif section == "Add Holding":

    st.subheader("➕ Add Holding")

    ticker = st.text_input(
        "Ticker",
        placeholder="e.g. NVDA",
        key="add_ticker",
    ).strip().upper()

    col1, col2 = st.columns(2)

    with col1:

        quantity = st.number_input(
            "Quantity",
            min_value=0.0,
            value=0.0,
            step=0.001,
            format="%.6f",
            key="add_quantity",
        )

    with col2:

        market_value = st.number_input(
            "Market Value",
            min_value=0.0,
            value=0.0,
            step=0.01,
            key="add_market_value",
        )

    name = st.text_input(
        "Name",
        placeholder="Optional",
        key="add_name",
    )

    asset_type = st.selectbox(
        "Asset Type",
        ASSET_TYPES,
        key="add_asset_type",
    )

    if st.button(
        "➕ Add Holding",
        type="primary",
        use_container_width=True,
        key="add_holding",
    ):

        if not ticker:

            st.error(
                "Ticker is required."
            )

        elif "Ticker" in holdings.columns and ticker in holdings["Ticker"].values:

            st.error(
                f"{ticker} already exists. "
                "Use Edit instead."
            )

        else:

            new_row = {
                "Ticker": ticker,
                "Quantity": quantity,
                "Market Value": market_value,
                "Name": name,
                "Asset Type": asset_type,
            }

            # Preserve the existing CSV schema.

            for column in holdings.columns:

                if column not in new_row:

                    new_row[column] = ""

            new_df = pd.DataFrame(
                [new_row]
            )

            new_df = new_df[
                holdings.columns
            ]

            st.session_state.holdings = pd.concat(
                [
                    holdings,
                    new_df,
                ],
                ignore_index=True,
            )

            if save_holdings(
                st.session_state.holdings
            ):

                st.success(
                    f"{ticker} added successfully."
                )

                st.rerun()


# ============================================================
# DELETE HOLDING
# ============================================================

elif section == "Delete Holding":

    st.subheader("🗑️ Delete Holding")

    if holdings.empty:

        st.info(
            "There are no holdings to delete."
        )

    else:

        selected_delete = st.selectbox(
            "Select Holding to Delete",
            holdings["Ticker"].tolist(),
            key="delete_ticker",
        )

        current_value = 0.0

        matching = holdings[
            holdings["Ticker"] == selected_delete
        ]

        if not matching.empty:

            current_value = numeric_value(
                matching.iloc[0].get(
                    "Market Value",
                    0
                )
            )

        st.warning(
            f"You are about to delete `{selected_delete}` "
            f"(current value £{current_value:,.2f})."
        )

        confirm_delete = st.checkbox(
            "I understand that this will remove the holding "
            "from holdings_raw.csv.",
            key="confirm_delete",
        )

        if st.button(
            "🗑️ Delete Holding",
            type="primary",
            use_container_width=True,
            key="delete_holding",
        ):

            if not confirm_delete:

                st.error(
                    "Please confirm deletion first."
                )

            else:

                st.session_state.holdings = (
                    st.session_state.holdings[
                        st.session_state.holdings["Ticker"]
                        != selected_delete
                    ]
                    .reset_index(drop=True)
                )

                if save_holdings(
                    st.session_state.holdings
                ):

                    st.success(
                        f"{selected_delete} deleted successfully."
                    )

                    st.rerun()
