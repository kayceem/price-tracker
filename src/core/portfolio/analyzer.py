"""
Comprehensive Portfolio Analyzer with FIFO P&L calculation and Interest Cost Analysis
"""

import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from collections import defaultdict

# Import configuration
from src.config.settings import config, INTEREST_RATE


class Transaction:
    """Represents a single transaction"""
    def __init__(self, scrip: str, date: datetime, trans_type: str,
                 quantity: float, price: float, description: str = ""):
        self.scrip = scrip
        self.date = date
        self.trans_type = trans_type  # BUY, SELL, IPO, BONUS, RIGHTS
        self.quantity = quantity
        self.price = price
        self.amount = quantity * price
        self.description = description

    def __repr__(self):
        return f"{self.date.date()} {self.scrip} {self.trans_type} {self.quantity}@{self.price}"


class HoldingLot:
    """Represents a lot of shares purchased at a specific time and price"""
    def __init__(self, scrip: str, date: datetime, quantity: float, price: float, trans_type: str):
        self.scrip = scrip
        self.date = date
        self.quantity = quantity
        self.original_quantity = quantity
        self.price = price
        self.trans_type = trans_type
        self.cost_basis = quantity * price

    def days_held(self, as_of_date: datetime = None) -> int:
        """Calculate days held"""
        if as_of_date is None:
            as_of_date = datetime.now()
        return (as_of_date - self.date).days

    def calculate_interest(self, rate: float, as_of_date: datetime = None) -> float:
        """Calculate interest cost for this lot"""
        days = self.days_held(as_of_date)
        return (self.cost_basis * rate / 100 * days / 365)

    def __repr__(self):
        return f"{self.date.date()} {self.quantity}/{self.original_quantity} @ {self.price}"


class PortfolioAnalyzer:
    """Main portfolio analyzer using FIFO method"""

    def __init__(self, username: str, csv_base_path: str = None):
        self.username = username

        # Set up paths
        if csv_base_path is None:
            self.base_dir = config.get_user_csv_dir(username)
        else:
            self.base_dir = Path(csv_base_path)

        self.history_dir = Path(self.base_dir, 'history')

        # Data storage
        self.transactions: List[Transaction] = []
        self.holdings: Dict[str, List[HoldingLot]] = defaultdict(list)  # Current holdings by scrip
        self.realized_pnl: Dict[str, float] = defaultdict(float)  # Realized P&L by scrip
        self.sold_cost_basis: Dict[str, float] = defaultdict(float)  # Cost basis of sold shares by scrip
        self.sold_interest: Dict[str, float] = defaultdict(float)  # Interest cost on sold shares by scrip
        self.sold_lots_info: Dict[str, List[Dict]] = defaultdict(list)  # Info about sold lots for analysis
        self.trade_history: List[Dict] = []  # All transactions for reporting

        # Load data
        self._load_transactions()
        self._process_transactions()

    def _extract_date_from_trade_id(self, trade_id: str) -> datetime:
        """Extract date from exchange trade ID (first 8 digits are YYYYMMDD)"""
        try:
            date_str = str(trade_id)[:8]
            return datetime.strptime(date_str, '%Y%m%d')
        except:
            return None

    def _parse_transaction_date(self, date_str: str) -> datetime:
        """Parse date from transaction history format (YYYY-MM-DD)"""
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except:
            return None

    def _categorize_transaction(self, description: str) -> str:
        """Categorize transaction type from description"""
        desc_upper = description.upper()

        if 'IPO' in desc_upper or 'INITIAL PUBLIC OFFERING' in desc_upper:
            return 'IPO'
        elif 'BONUS' in desc_upper or 'CA-BONUS' in desc_upper:
            return 'BONUS'
        elif 'RIGHTS' in desc_upper or 'CA-RIGHTS' in desc_upper:
            return 'RIGHTS'
        elif 'ON-CR' in desc_upper or 'BUY' in desc_upper:
            return 'BUY'
        elif 'ON-DR' in desc_upper or 'SELL' in desc_upper:
            return 'SELL'
        else:
            return 'UNKNOWN'

    def _load_transactions(self):
        """Load all transactions from CSV files"""

        # Load Trade Book Details
        trade_book_path = Path(self.history_dir, 'Trade Book Details.csv')
        if trade_book_path.exists():
            trade_df = pd.read_csv(trade_book_path)

            for _, row in trade_df.iterrows():
                # Extract date from trade ID
                date = self._extract_date_from_trade_id(row['EXCHANGE TRADE ID'])
                if date is None:
                    continue

                trans_type = 'BUY' if row['BUY/SELL'] == 'Buy' else 'SELL'

                trans = Transaction(
                    scrip=row['SYMBOL'],
                    date=date,
                    trans_type=trans_type,
                    quantity=float(row['TRADE QTY']),
                    price=float(row['PRICE(NPR)']),
                    description=f"Trade Book: {row['BUY/SELL']}"
                )
                self.transactions.append(trans)

        # Load Transaction History (includes IPO, Bonus, Rights)
        trans_history_path = Path(self.history_dir, 'Transaction History.csv')
        if trans_history_path.exists():
            trans_df = pd.read_csv(trans_history_path)

            for _, row in trans_df.iterrows():
                date = self._parse_transaction_date(row['Transaction Date'])
                if date is None:
                    continue

                # Determine if it's credit (buy) or debit (sell)
                credit = row['Credit Quantity']
                debit = row['Debit Quantity']

                # Categorize transaction type
                trans_type = self._categorize_transaction(row['History Description'])

                # Handle credit transactions (acquisitions)
                if credit and credit != '-':
                    quantity = float(credit)

                    # Set price based on transaction type
                    if trans_type in ['IPO', 'BONUS', 'RIGHTS']:
                        price = 100.0  # Fixed price for IPO/Bonus/Rights
                    else:
                        # For market buys, we should have the price from trade book
                        # Skip if already added from trade book
                        continue

                    trans = Transaction(
                        scrip=row['Scrip'],
                        date=date,
                        trans_type=trans_type,
                        quantity=quantity,
                        price=price,
                        description=row['History Description']
                    )
                    self.transactions.append(trans)

                # Handle debit transactions (sells)
                elif debit and debit != '-':
                    # Sells are already handled by trade book, skip
                    continue

        # Sort all transactions by date
        self.transactions.sort(key=lambda x: x.date)

    def _process_transactions(self):
        """Process all transactions using FIFO method"""

        for trans in self.transactions:
            self.trade_history.append({
                'Date': trans.date,
                'Scrip': trans.scrip,
                'Type': trans.trans_type,
                'Quantity': trans.quantity,
                'Price': trans.price,
                'Amount': trans.amount,
                'Description': trans.description
            })

            if trans.trans_type in ['BUY', 'IPO', 'BONUS', 'RIGHTS']:
                # Add to holdings
                lot = HoldingLot(
                    scrip=trans.scrip,
                    date=trans.date,
                    quantity=trans.quantity,
                    price=trans.price,
                    trans_type=trans.trans_type
                )
                self.holdings[trans.scrip].append(lot)

            elif trans.trans_type == 'SELL':
                # FIFO: Sell from earliest lots first
                self._process_sell(trans)

    def _process_sell(self, sell_trans: Transaction):
        """Process a sell transaction using FIFO"""
        scrip = sell_trans.scrip
        remaining_to_sell = sell_trans.quantity
        sell_proceeds = sell_trans.amount
        total_cost_basis = 0.0
        total_interest = 0.0

        # Get lots for this scrip (already sorted by date due to transaction sorting)
        lots = self.holdings[scrip]

        while remaining_to_sell > 0 and lots:
            oldest_lot = lots[0]

            if oldest_lot.quantity <= remaining_to_sell:
                # Sell entire lot
                quantity_sold = oldest_lot.quantity
                cost_basis = oldest_lot.cost_basis

                # Calculate interest for this sold lot (from purchase to sale date)
                interest_cost = oldest_lot.calculate_interest(INTEREST_RATE, sell_trans.date)

                remaining_to_sell -= quantity_sold
                total_cost_basis += cost_basis
                total_interest += interest_cost

                # Store info about sold lot
                self.sold_lots_info[scrip].append({
                    'purchase_date': oldest_lot.date,
                    'sell_date': sell_trans.date,
                    'quantity': quantity_sold,
                    'purchase_price': oldest_lot.price,
                    'sell_price': sell_trans.price,
                    'cost_basis': cost_basis,
                    'interest_cost': interest_cost,
                    'days_held': (sell_trans.date - oldest_lot.date).days,
                    'trans_type': oldest_lot.trans_type
                })

                # Remove the lot
                lots.pop(0)
            else:
                # Partial sale from this lot
                quantity_sold = remaining_to_sell
                cost_per_share = oldest_lot.price
                cost_basis = quantity_sold * cost_per_share

                # Calculate interest for the portion sold
                days_held = (sell_trans.date - oldest_lot.date).days
                interest_cost = (cost_basis * INTEREST_RATE / 100 * days_held / 365)

                total_cost_basis += cost_basis
                total_interest += interest_cost

                # Store info about sold lot
                self.sold_lots_info[scrip].append({
                    'purchase_date': oldest_lot.date,
                    'sell_date': sell_trans.date,
                    'quantity': quantity_sold,
                    'purchase_price': oldest_lot.price,
                    'sell_price': sell_trans.price,
                    'cost_basis': cost_basis,
                    'interest_cost': interest_cost,
                    'days_held': days_held,
                    'trans_type': oldest_lot.trans_type
                })

                # Reduce lot quantity
                oldest_lot.quantity -= quantity_sold
                oldest_lot.cost_basis -= cost_basis

                remaining_to_sell = 0

        # Track the cost basis and interest of sold shares
        self.sold_cost_basis[scrip] += total_cost_basis
        self.sold_interest[scrip] += total_interest

        # Calculate realized P&L
        realized_pnl = sell_proceeds - total_cost_basis
        self.realized_pnl[scrip] += realized_pnl

    def get_current_holdings_summary(self, current_prices: Dict[str, float] = None) -> pd.DataFrame:
        """Get summary of current holdings"""

        holdings_data = []

        for scrip, lots in self.holdings.items():
            if not lots:
                continue

            total_quantity = sum(lot.quantity for lot in lots)
            total_cost = sum(lot.cost_basis for lot in lots)
            avg_price = total_cost / total_quantity if total_quantity > 0 else 0

            # Calculate weighted average days held
            total_days_weighted = sum(lot.quantity * lot.days_held() for lot in lots)
            avg_days_held = total_days_weighted / total_quantity if total_quantity > 0 else 0

            # Calculate interest cost
            total_interest = sum(lot.calculate_interest(INTEREST_RATE) for lot in lots)

            # Get current price if available
            current_price = current_prices.get(scrip) if current_prices else None
            current_value = total_quantity * current_price if current_price else None
            unrealized_pnl = current_value - total_cost if current_value else None

            # Get earliest purchase date
            earliest_date = min(lot.date for lot in lots)

            holdings_data.append({
                'Scrip': scrip,
                'Quantity': total_quantity,
                'Avg Cost': round(avg_price, 2),
                'Total Cost': round(total_cost, 2),
                'Earliest Purchase': earliest_date.date(),
                'Avg Days Held': round(avg_days_held, 1),
                'Interest Cost': round(total_interest, 2),
                'Current Price': current_price,
                'Current Value': round(current_value, 2) if current_value else None,
                'Unrealized P&L': round(unrealized_pnl, 2) if unrealized_pnl else None,
                'Unrealized P&L %': round(unrealized_pnl / total_cost * 100, 2) if unrealized_pnl and total_cost > 0 else None
            })

        return pd.DataFrame(holdings_data)

    def get_portfolio_summary(self, current_prices: Dict[str, float] = None, wacc_data: Dict[str, Dict] = None) -> pd.DataFrame:
        """Get comprehensive portfolio summary by scrip"""

        summary_data = []

        # Get all unique scrips (both current holdings and sold positions)
        all_scrips = set(self.holdings.keys()) | set(self.realized_pnl.keys())

        for scrip in all_scrips:
            # Current holdings
            lots = self.holdings.get(scrip, [])
            current_qty = sum(lot.quantity for lot in lots)
            current_holdings_cost = sum(lot.cost_basis for lot in lots)
            avg_cost = current_holdings_cost / current_qty if current_qty > 0 else 0

            # Interest on current holdings
            interest_current = sum(lot.calculate_interest(INTEREST_RATE) for lot in lots)

            # Realized P&L
            realized = self.realized_pnl.get(scrip, 0)

            # Cost basis of sold shares
            sold_cost = self.sold_cost_basis.get(scrip, 0)

            # Unrealized P&L
            current_price = current_prices.get(scrip) if current_prices else None
            current_value = current_qty * current_price if current_price and current_qty > 0 else 0
            unrealized = current_value - current_holdings_cost if current_qty > 0 else 0

            # Total P&L
            total_pnl = realized + unrealized

            # Total investment (current holdings + sold shares cost basis)
            total_investment = current_holdings_cost + sold_cost

            # Net P&L after interest
            net_pnl = total_pnl - interest_current

            # Return percentages (based on total investment including sold shares)
            total_return_pct = (total_pnl / total_investment * 100) if total_investment > 0 else 0
            net_return_pct = (net_pnl / total_investment * 100) if total_investment > 0 else 0

            # Get 52-week high/low from wacc_data if available
            week_52_high = None
            week_52_low = None
            if wacc_data and scrip in wacc_data:
                week_52_high = wacc_data[scrip].get('High')
                week_52_low = wacc_data[scrip].get('Low')

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
        # Sort by total investment descending
        df = df.sort_values('Total Investment', ascending=False)

        return df

    def get_transaction_history(self) -> pd.DataFrame:
        """Get complete transaction history"""
        df = pd.DataFrame(self.trade_history)
        if not df.empty:
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
        return df

    def get_detailed_lots(self, current_prices: Dict[str, float] = None) -> pd.DataFrame:
        """Get detailed information about each holding lot"""

        lots_data = []

        for scrip, lots in self.holdings.items():
            current_price = current_prices.get(scrip) if current_prices else None

            for lot in lots:
                current_value = lot.quantity * current_price if current_price else None
                unrealized_pnl = current_value - lot.cost_basis if current_value else None
                interest = lot.calculate_interest(INTEREST_RATE)
                net_pnl = unrealized_pnl - interest if unrealized_pnl else None

                lots_data.append({
                    'Scrip': scrip,
                    'Purchase Date': lot.date.date(),
                    'Type': lot.trans_type,
                    'Quantity': lot.quantity,
                    'Purchase Price': lot.price,
                    'Cost Basis': round(lot.cost_basis, 2),
                    'Days Held': lot.days_held(),
                    'Interest Cost': round(interest, 2),
                    'Current Price': current_price,
                    'Current Value': round(current_value, 2) if current_value else None,
                    'Unrealized P&L': round(unrealized_pnl, 2) if unrealized_pnl else None,
                    'Net P&L (After Interest)': round(net_pnl, 2) if net_pnl else None
                })

        df = pd.DataFrame(lots_data)
        if not df.empty:
            df = df.sort_values(['Scrip', 'Purchase Date'])

        return df

    def get_interest_analysis(self) -> pd.DataFrame:
        """Get detailed interest cost analysis for current holdings"""

        interest_data = []

        for scrip, lots in self.holdings.items():
            if not lots:
                continue

            total_investment = sum(lot.cost_basis for lot in lots)
            total_quantity = sum(lot.quantity for lot in lots)
            total_interest = sum(lot.calculate_interest(INTEREST_RATE) for lot in lots)

            # Calculate weighted average days held
            total_days_weighted = sum(lot.quantity * lot.days_held() for lot in lots)
            avg_days_held = total_days_weighted / total_quantity if total_quantity > 0 else 0

            interest_data.append({
                'Scrip': scrip,
                'Investment Amount': round(total_investment, 2),
                'Avg Days Held': round(avg_days_held, 1),
                'Interest Rate %': INTEREST_RATE,
                'Interest Cost': round(total_interest, 2),
                'Interest % of Investment': round(total_interest / total_investment * 100, 2) if total_investment > 0 else 0
            })

        df = pd.DataFrame(interest_data)
        if not df.empty:
            df = df.sort_values('Interest Cost', ascending=False)

        return df

    def get_sold_interest_analysis(self) -> pd.DataFrame:
        """Get detailed interest cost analysis for sold stocks"""

        interest_data = []

        for scrip, sold_lots in self.sold_lots_info.items():
            if not sold_lots:
                continue

            total_investment = sum(lot['cost_basis'] for lot in sold_lots)
            total_quantity = sum(lot['quantity'] for lot in sold_lots)
            total_interest = sum(lot['interest_cost'] for lot in sold_lots)

            # Calculate weighted average days held
            total_days_weighted = sum(lot['quantity'] * lot['days_held'] for lot in sold_lots)
            avg_days_held = total_days_weighted / total_quantity if total_quantity > 0 else 0

            # Get realized P&L for this scrip
            realized_pnl = self.realized_pnl.get(scrip, 0)

            interest_data.append({
                'Scrip': scrip,
                'Total Sold Quantity': total_quantity,
                'Investment Amount': round(total_investment, 2),
                'Avg Days Held': round(avg_days_held, 1),
                'Interest Rate %': INTEREST_RATE,
                'Interest Cost': round(total_interest, 2),
                'Interest % of Investment': round(total_interest / total_investment * 100, 2) if total_investment > 0 else 0,
                'Realized P&L': round(realized_pnl, 2),
                'Net P&L (After Interest)': round(realized_pnl - total_interest, 2)
            })

        df = pd.DataFrame(interest_data)
        if not df.empty:
            df = df.sort_values('Interest Cost', ascending=False)

        return df

    def generate_reports(self, output_dir: Path = None):
        """Generate all CSV reports"""

        if output_dir is None:
            output_dir = self.base_dir

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Load current prices and wacc data from Wacc Rates if available
        current_prices = {}
        wacc_data = {}
        wacc_path = Path(self.base_dir, 'Wacc Rates.csv')
        if wacc_path.exists():
            wacc_df = pd.read_csv(wacc_path)
            for _, row in wacc_df.iterrows():
                scrip = row['Scrip']
                if pd.notna(row.get('LTP')):
                    current_prices[scrip] = float(row['LTP'])
                wacc_data[scrip] = {
                    'High': float(row['High']) if pd.notna(row.get('High')) else None,
                    'Low': float(row['Low']) if pd.notna(row.get('Low')) else None
                }

        # Generate reports
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

        # 4. Detailed Lots
        lots = self.get_detailed_lots(current_prices)
        lots_path = Path(output_dir, 'detailed_holdings_lots.csv')
        lots.to_csv(lots_path, index=False)
        print(f"✓ Detailed Holdings Lots: {lots_path}")

        # 5. Interest Analysis
        interest = self.get_interest_analysis()
        interest_path = Path(output_dir, 'interest_analysis.csv')
        interest.to_csv(interest_path, index=False)
        print(f"✓ Interest Analysis: {interest_path}")

        # Print summary statistics
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

            print(f"Total Investment:        Rs. {total_investment:,.2f}")
            print(f"Current Value:           Rs. {total_current_value:,.2f}")
            print(f"Realized P&L:            Rs. {total_realized:,.2f}")
            print(f"Unrealized P&L:          Rs. {total_unrealized:,.2f}")
            print(f"Total P&L:               Rs. {total_pnl:,.2f}")
            print(f"Interest Cost ({INTEREST_RATE}%):   Rs. {total_interest:,.2f}")
            print(f"Net P&L (After Interest): Rs. {net_pnl:,.2f}")
            print(f"\nTotal Return:            {total_pnl/total_investment*100:.2f}%")
            print(f"Net Return:              {net_pnl/total_investment*100:.2f}%")

        print("="*60)

        return {
            'portfolio_summary': portfolio_summary,
            'transaction_history': transaction_history,
            'current_holdings': holdings,
            'detailed_lots': lots,
            'interest_analysis': interest
        }


if __name__ == '__main__':
    # Example usage
    username = '3522757'

    analyzer = PortfolioAnalyzer(username)
    reports = analyzer.generate_reports()
