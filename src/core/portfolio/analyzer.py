"""
Portfolio Analyzer using Wacc Rates.csv as source of truth for holdings
and Trade Book Details for transaction history and realized P&L
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from collections import defaultdict

# Import configuration
from src.config.settings import config, INTEREST_RATE


class PortfolioAnalyzer:
    """Portfolio analyzer using Wacc Rates.csv and Trade Book Details"""

    def __init__(self, username: str, csv_base_path: str = None):
        self.username = username

        # Set up paths
        if csv_base_path is None:
            self.base_dir = config.get_user_csv_dir(username)
        else:
            self.base_dir = Path(csv_base_path)

        self.history_dir = Path(self.base_dir, 'history')

        # Load data
        self.wacc_df = self._load_wacc_rates()
        self.trade_book_df = self._load_trade_book()
        self.transaction_history_df = self._load_transaction_history()

    def _load_wacc_rates(self) -> pd.DataFrame:
        """Load Wacc Rates.csv - source of truth for current holdings"""
        wacc_path = Path(self.base_dir, 'Wacc Rates.csv')
        if wacc_path.exists():
            df = pd.read_csv(wacc_path)
            # Only keep rows with actual holdings (Balance > 0)
            df = df[df['Balance'] > 0].copy()
            return df
        return pd.DataFrame()

    def _load_trade_book(self) -> pd.DataFrame:
        """Load Trade Book Details.csv"""
        trade_path = Path(self.history_dir, 'Trade Book Details.csv')
        if trade_path.exists():
            df = pd.read_csv(trade_path)
            # Extract date from EXCHANGE TRADE ID (first 8 digits YYYYMMDD)
            df['Date'] = pd.to_datetime(df['EXCHANGE TRADE ID'].astype(str).str[:8], format='%Y%m%d', errors='coerce')
            return df
        return pd.DataFrame()

    def _load_transaction_history(self) -> pd.DataFrame:
        """Load Transaction History.csv"""
        trans_path = Path(self.history_dir, 'Transaction History.csv')
        if trans_path.exists():
            df = pd.read_csv(trans_path)
            df['Transaction Date'] = pd.to_datetime(df['Transaction Date'], errors='coerce')
            return df
        return pd.DataFrame()

    def get_current_holdings_summary(self, current_prices: Dict[str, float] = None) -> pd.DataFrame:
        """Get current holdings from Wacc Rates with additional calculated fields"""
        if self.wacc_df.empty:
            return pd.DataFrame()

        holdings_data = []

        for _, row in self.wacc_df.iterrows():
            scrip = row['Scrip']
            quantity = float(row['Balance'])
            wacc = float(row['WACC'])
            investment = float(row['Investment'])

            # Get LTP from current_prices or use LTP from Wacc file
            ltp = current_prices.get(scrip) if current_prices else float(row.get('LTP', 0))
            current_value = quantity * ltp if ltp else float(row.get('Current Value', 0))
            unrealized_pnl = float(row.get('Profit/Loss', current_value - investment))

            # Calculate first purchase date and days held from trade book
            scrip_trades = self.trade_book_df[self.trade_book_df['SYMBOL'] == scrip]
            buy_trades = scrip_trades[scrip_trades['BUY/SELL'] == 'Buy']

            if not buy_trades.empty:
                first_purchase = buy_trades['Date'].min()
                days_held = (datetime.now() - first_purchase).days
            else:
                first_purchase = None
                days_held = 0

            # Calculate interest
            interest = (investment * INTEREST_RATE / 100 * days_held / 365) if days_held > 0 else 0

            holdings_data.append({
                'Scrip': scrip,
                'Quantity': quantity,
                'Avg Cost': round(wacc, 2),
                'Total Cost': round(investment, 2),
                'First Purchase': first_purchase.date() if first_purchase else None,
                'Days Held': days_held,
                'Interest Cost': round(interest, 2),
                'Current Price': ltp,
                'Current Value': round(current_value, 2),
                'Unrealized P&L': round(unrealized_pnl, 2),
                'Unrealized P&L %': round((unrealized_pnl / investment * 100), 2) if investment > 0 else 0
            })

        return pd.DataFrame(holdings_data)

    def get_portfolio_summary(self, current_prices: Dict[str, float] = None, wacc_data: Dict[str, Dict] = None) -> pd.DataFrame:
        """Get comprehensive portfolio summary including realized P&L from trade book"""

        # Get current holdings
        holdings_df = self.get_current_holdings_summary(current_prices)

        # Calculate realized P&L from trade book
        realized_pnl_by_scrip = self._calculate_realized_pnl()

        # Get all unique scrips (current holdings + sold positions)
        all_scrips = set(holdings_df['Scrip'].tolist()) | set(realized_pnl_by_scrip.keys())

        summary_data = []

        for scrip in all_scrips:
            # Current holdings info
            if scrip in holdings_df['Scrip'].values:
                holding = holdings_df[holdings_df['Scrip'] == scrip].iloc[0]
                current_qty = holding['Quantity']
                avg_cost = holding['Avg Cost']
                current_holdings_cost = holding['Total Cost']
                interest_current = holding['Interest Cost']
                current_price = holding['Current Price']
                current_value = holding['Current Value']
                unrealized = holding['Unrealized P&L']
            else:
                current_qty = 0
                avg_cost = 0
                current_holdings_cost = 0
                interest_current = 0
                current_price = current_prices.get(scrip) if current_prices else 0
                current_value = 0
                unrealized = 0

            # Realized P&L
            realized_info = realized_pnl_by_scrip.get(scrip, {'realized_pnl': 0, 'sold_cost_basis': 0})
            realized = realized_info['realized_pnl']
            sold_cost = realized_info['sold_cost_basis']

            # Totals
            total_investment = current_holdings_cost + sold_cost
            total_pnl = realized + unrealized
            net_pnl = total_pnl - interest_current

            # Percentages
            total_return_pct = (total_pnl / total_investment * 100) if total_investment > 0 else 0
            net_return_pct = (net_pnl / total_investment * 100) if total_investment > 0 else 0

            # 52-week high/low
            week_52_high = None
            week_52_low = None
            if not self.wacc_df.empty and scrip in self.wacc_df['Scrip'].values:
                wacc_row = self.wacc_df[self.wacc_df['Scrip'] == scrip].iloc[0]
                week_52_high = float(wacc_row.get('High', 0)) if pd.notna(wacc_row.get('High')) else None
                week_52_low = float(wacc_row.get('Low', 0)) if pd.notna(wacc_row.get('Low')) else None

            summary_data.append({
                'Scrip': scrip,
                'Current Holdings': current_qty,
                'Avg Cost': round(avg_cost, 2),
                'Total Investment': round(total_investment, 2),
                'Current Price': current_price,
                'Current Value': round(current_value, 2),
                'Realized P&L': round(realized, 2),
                'Unrealized P&L': round(unrealized, 2),
                'Total P&L': round(total_pnl, 2),
                'Interest Cost': round(interest_current, 2),
                'Net P&L (After Interest)': round(net_pnl, 2),
                'Total Return %': round(total_return_pct, 2),
                'Net Return %': round(net_return_pct, 2),
                '52 Week High': week_52_high,
                '52 Week Low': week_52_low
            })

        df = pd.DataFrame(summary_data)
        if not df.empty:
            df = df.sort_values('Total Investment', ascending=False)
        return df

    def _calculate_realized_pnl(self) -> Dict[str, Dict]:
        """Calculate realized P&L from trade book using FIFO for sold shares"""
        if self.trade_book_df.empty:
            return {}

        realized_by_scrip = {}

        # Group by scrip
        for scrip in self.trade_book_df['SYMBOL'].unique():
            scrip_trades = self.trade_book_df[self.trade_book_df['SYMBOL'] == scrip].sort_values('Date')

            # FIFO queue for tracking purchases
            purchase_queue = []
            total_realized_pnl = 0
            total_sold_cost_basis = 0

            for _, trade in scrip_trades.iterrows():
                qty = float(trade['TRADE QTY'])
                price = float(trade['PRICE(NPR)'])

                if trade['BUY/SELL'] == 'Buy':
                    # Add to purchase queue
                    purchase_queue.append({'qty': qty, 'price': price})

                elif trade['BUY/SELL'] == 'Sell':
                    # Sell using FIFO
                    remaining_to_sell = qty
                    sell_proceeds = qty * price
                    cost_basis = 0

                    while remaining_to_sell > 0 and purchase_queue:
                        oldest_purchase = purchase_queue[0]

                        if oldest_purchase['qty'] <= remaining_to_sell:
                            # Sell entire purchase
                            cost_basis += oldest_purchase['qty'] * oldest_purchase['price']
                            remaining_to_sell -= oldest_purchase['qty']
                            purchase_queue.pop(0)
                        else:
                            # Partial sell
                            cost_basis += remaining_to_sell * oldest_purchase['price']
                            oldest_purchase['qty'] -= remaining_to_sell
                            remaining_to_sell = 0

                    realized_pnl = sell_proceeds - cost_basis
                    total_realized_pnl += realized_pnl
                    total_sold_cost_basis += cost_basis

            if total_realized_pnl != 0 or total_sold_cost_basis != 0:
                realized_by_scrip[scrip] = {
                    'realized_pnl': total_realized_pnl,
                    'sold_cost_basis': total_sold_cost_basis
                }

        return realized_by_scrip

    def get_transaction_history(self) -> pd.DataFrame:
        """Get transaction history combining Trade Book and Transaction History"""
        transactions = []

        # Add Trade Book transactions
        if not self.trade_book_df.empty:
            for _, row in self.trade_book_df.iterrows():
                transactions.append({
                    'Date': row['Date'],
                    'Scrip': row['SYMBOL'],
                    'Type': row['BUY/SELL'].upper(),
                    'Quantity': float(row['TRADE QTY']),
                    'Price': float(row['PRICE(NPR)']),
                    'Amount': float(row['Value(NPR)']),
                    'Description': f"Trade Book: {row['BUY/SELL']}"
                })

        # Add IPO/BONUS from Transaction History
        if not self.transaction_history_df.empty:
            for _, row in self.transaction_history_df.iterrows():
                desc = str(row['History Description']).upper()

                if 'IPO' in desc or 'INITIAL PUBLIC OFFERING' in desc:
                    credit = row.get('Credit Quantity')
                    if credit and credit != '-':
                        qty = float(credit)
                        transactions.append({
                            'Date': row['Transaction Date'],
                            'Scrip': row['Scrip'],
                            'Type': 'IPO',
                            'Quantity': qty,
                            'Price': 100.0,
                            'Amount': qty * 100.0,
                            'Description': row['History Description']
                        })

                elif 'BONUS' in desc or 'CA-BONUS' in desc:
                    credit = row.get('Credit Quantity')
                    if credit and credit != '-':
                        qty = float(credit)
                        transactions.append({
                            'Date': row['Transaction Date'],
                            'Scrip': row['Scrip'],
                            'Type': 'BONUS',
                            'Quantity': qty,
                            'Price': 0.0,
                            'Amount': 0.0,
                            'Description': row['History Description']
                        })

        df = pd.DataFrame(transactions)
        if not df.empty:
            df = df.sort_values('Date', ascending=False)
        return df

    def get_detailed_pools(self, current_prices: Dict[str, float] = None) -> pd.DataFrame:
        """Get detailed pools - only showing current holdings (Balance > 0)"""
        # This is the same as current holdings summary with different column names
        return self.get_current_holdings_summary(current_prices).rename(columns={
            'First Purchase': 'First Purchase Date',
            'Total Cost': 'Total Cost Basis',
            'Avg Cost': 'Avg Purchase Price'
        }).assign(**{
            'Last Purchase Date': lambda x: x['First Purchase Date'],  # Approximate
            'Net P&L (After Interest)': lambda x: x['Unrealized P&L'] - x['Interest Cost']
        })

    def get_interest_analysis(self) -> pd.DataFrame:
        """Get interest analysis for current holdings"""
        holdings = self.get_current_holdings_summary()

        if holdings.empty:
            return pd.DataFrame()

        interest_data = []
        for _, row in holdings.iterrows():
            interest_data.append({
                'Scrip': row['Scrip'],
                'Investment Amount': row['Total Cost'],
                'Days Held': row['Days Held'],
                'Interest Rate %': INTEREST_RATE,
                'Interest Cost': row['Interest Cost'],
                'Interest % of Investment': round((row['Interest Cost'] / row['Total Cost'] * 100), 2) if row['Total Cost'] > 0 else 0
            })

        df = pd.DataFrame(interest_data)
        if not df.empty:
            df = df.sort_values('Interest Cost', ascending=False)
        return df

    def get_sold_interest_analysis(self) -> pd.DataFrame:
        """Get interest analysis for sold positions"""
        # Calculate from trade book
        realized = self._calculate_realized_pnl()

        sold_data = []
        for scrip, info in realized.items():
            if info['sold_cost_basis'] <= 0:
                continue

            # Get sold trades for this scrip
            scrip_trades = self.trade_book_df[self.trade_book_df['SYMBOL'] == scrip]
            sell_trades = scrip_trades[scrip_trades['BUY/SELL'] == 'Sell']
            buy_trades = scrip_trades[scrip_trades['BUY/SELL'] == 'Buy']

            if sell_trades.empty or buy_trades.empty:
                continue

            # Calculate average days held for sold shares
            first_buy = buy_trades['Date'].min()
            last_sell = sell_trades['Date'].max()
            avg_days_held = (last_sell - first_buy).days

            # Calculate interest on sold shares
            interest = info['sold_cost_basis'] * INTEREST_RATE / 100 * avg_days_held / 365

            total_qty_sold = sell_trades['TRADE QTY'].sum()

            sold_data.append({
                'Scrip': scrip,
                'Total Sold Quantity': total_qty_sold,
                'Investment Amount': round(info['sold_cost_basis'], 2),
                'Avg Days Held': round(avg_days_held, 1),
                'Interest Rate %': INTEREST_RATE,
                'Interest Cost': round(interest, 2),
                'Interest % of Investment': round((interest / info['sold_cost_basis'] * 100), 2) if info['sold_cost_basis'] > 0 else 0,
                'Realized P&L': round(info['realized_pnl'], 2),
                'Net P&L (After Interest)': round(info['realized_pnl'] - interest, 2)
            })

        df = pd.DataFrame(sold_data)
        if not df.empty:
            df = df.sort_values('Interest Cost', ascending=False)
        return df

    def generate_reports(self, output_dir: Path = None):
        """Generate all CSV reports"""

        if output_dir is None:
            output_dir = self.base_dir / 'reports'

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get current prices from Wacc Rates
        current_prices = {}
        wacc_data = {}
        if not self.wacc_df.empty:
            for _, row in self.wacc_df.iterrows():
                scrip = row['Scrip']
                current_prices[scrip] = float(row.get('LTP', 0))
                wacc_data[scrip] = {
                    'High': float(row.get('High', 0)) if pd.notna(row.get('High')) else None,
                    'Low': float(row.get('Low', 0)) if pd.notna(row.get('Low')) else None
                }

        print(f"Generating portfolio reports for user {self.username}...")
        print(f"Using interest rate: {INTEREST_RATE}%")

        # 1. Portfolio Summary
        portfolio_summary = self.get_portfolio_summary(current_prices, wacc_data)
        summary_path = Path(output_dir, 'portfolio_summary.csv')
        portfolio_summary.to_csv(summary_path, index=False)
        print(f"✓ Portfolio Summary: {summary_path}")

        # 2. Transaction History
        transaction_history = self.get_transaction_history()
        trans_path = Path(output_dir, 'transaction_history.csv')
        transaction_history.to_csv(trans_path, index=False)
        print(f"✓ Transaction History: {trans_path}")

        # 3. Current Holdings
        holdings = self.get_current_holdings_summary(current_prices)
        holdings_path = Path(output_dir, 'current_holdings.csv')
        holdings.to_csv(holdings_path, index=False)
        print(f"✓ Current Holdings: {holdings_path}")

        # 4. Detailed Pools
        pools = self.get_detailed_pools(current_prices)
        pools_path = Path(output_dir, 'detailed_holdings_pools.csv')
        pools.to_csv(pools_path, index=False)
        print(f"✓ Detailed Holdings Pools: {pools_path}")

        # 5. Interest Analysis
        interest = self.get_interest_analysis()
        interest_path = Path(output_dir, 'interest_analysis.csv')
        interest.to_csv(interest_path, index=False)
        print(f"✓ Interest Analysis: {interest_path}")

        # Print summary
        print("\n" + "="*60)
        print("PORTFOLIO SUMMARY")
        print("="*60)

        if not portfolio_summary.empty:
            total_investment = portfolio_summary['Total Investment'].sum()
            total_current_value = portfolio_summary['Current Value'].sum()
            total_realized = portfolio_summary['Realized P&L'].sum()
            total_unrealized = portfolio_summary['Unrealized P&L'].sum()
            total_pnl = portfolio_summary['Total P&L'].sum()
            total_interest = portfolio_summary['Interest Cost'].sum()
            net_pnl = portfolio_summary['Net P&L (After Interest)'].sum()

            print(f"Total Investment:         Rs. {total_investment:,.2f}")
            print(f"Current Value:            Rs. {total_current_value:,.2f}")
            print(f"Realized P&L:             Rs. {total_realized:,.2f}")
            print(f"Unrealized P&L:           Rs. {total_unrealized:,.2f}")
            print(f"Total P&L:                Rs. {total_pnl:,.2f}")
            print(f"Interest Cost ({INTEREST_RATE}%):    Rs. {total_interest:,.2f}")
            print(f"Net P&L (After Interest): Rs. {net_pnl:,.2f}")
            print(f"\nTotal Return:             {(total_pnl/total_investment*100):.2f}%")
            print(f"Net Return:               {(net_pnl/total_investment*100):.2f}%")

        print("="*60)

        return {
            'portfolio_summary': portfolio_summary,
            'transaction_history': transaction_history,
            'current_holdings': holdings,
            'detailed_pools': pools,
            'interest_analysis': interest
        }


# Helper functions for API compatibility
def get_current_prices_from_db() -> Dict[str, float]:
    """Fetch current prices from Wacc Rates.csv for now"""
    # TODO: Implement database fetching later
    analyzer = PortfolioAnalyzer(config.username)
    if analyzer.wacc_df.empty:
        return {}
    return {row['Scrip']: float(row['LTP']) for _, row in analyzer.wacc_df.iterrows()}


def get_wacc_data_from_db() -> Dict[str, Dict]:
    """Fetch 52-week high/low from Wacc Rates.csv for now"""
    # TODO: Implement database fetching later
    analyzer = PortfolioAnalyzer(config.username)
    if analyzer.wacc_df.empty:
        return {}

    wacc_data = {}
    for _, row in analyzer.wacc_df.iterrows():
        scrip = row['Scrip']
        wacc_data[scrip] = {
            'High': float(row.get('High', 0)) if pd.notna(row.get('High')) else None,
            'Low': float(row.get('Low', 0)) if pd.notna(row.get('Low')) else None
        }
    return wacc_data


if __name__ == '__main__':
    username = '3522757'
    analyzer = PortfolioAnalyzer(username)
    reports = analyzer.generate_reports()
