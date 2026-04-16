from src.modules.portfolio.service import PortfolioQueryService as PortfolioAnalyzer


def get_current_prices_from_db():
    return PortfolioAnalyzer().get_current_prices()


def get_wacc_data_from_db():
    return PortfolioAnalyzer().get_wacc_snapshot()
