import bt
import pandas as pd
import logging

class RunSemiAnnually(bt.algos.RunPeriod):
    """
    Returns True on a half-year change (Jan or July).
    """
    def compare_dates(self, now, date_to_compare):
        # If the year changed, it's a new period
        if now.year != date_to_compare.year:
            return True
            
        # Check if we crossed the H1/H2 boundary (Months 1-6 vs 7-12)
        # We check if the 'half' of the year is different
        now_half = 1 if now.month <= 6 else 2
        comp_half = 1 if date_to_compare.month <= 6 else 2
        
        return now_half != comp_half

class TwoTradeRangeRebalancer(bt.Algo):
    def __init__(self, meta_df):
        super().__init__()
        self.meta = meta_df

    def __call__(self, target):
        targets = target.temp.get('weights')
        
        if not targets or target.value <= 0:
            return False

        if not target.children:
            print(f"INITIAL INVESTMENT | {target.now} | Entering positions...")
            return True 
        
        if 'stddev' not in self.meta.columns:
            raise KeyError("'stddev' column missing from assets metadata")

        breached_asset = None
        
        # 1. Find the first breach
        for cname, target_w in targets.items():
            if cname in target.children and cname in self.meta.index:
                actual_w = target.children[cname].weight
                sd = self.meta.loc[cname, 'stddev']
                upper_lim = target_w * (1 + sd)
                lower_lim = target_w * (1 - sd)
                if actual_w > upper_lim or actual_w < lower_lim:
                    breached_asset = cname
                    # print(f"TRIGGERED {target.now:%Y-%m-%d}: {cname}, {upper_lim:.4f} <-> {lower_lim:.4f} drifted to {actual_w:.4f}")
                    break

        if not breached_asset:
            return False

        # 2. Find the "Best Counterparty" 
        # (The one whose drift is furthest in the opposite direction)
        # If breached_asset is overweight, find the most underweight asset.
        breach_drift = target.children[breached_asset].weight - targets[breached_asset]
        
        best_counterparty = None
        max_opposing_drift = 0
        
        for cname, target_w in targets.items():
            if cname == breached_asset or cname not in target.children:
                continue
            
            # Distance from target (positive = overweight, negative = underweight)
            current_drift = target.children[cname].weight - target_w
            
            # If breach is +, we want the most - drift. If breach is -, we want the most + drift.
            # Effectively, we want to maximize the distance between the two drifts.
            drift_diff = abs(breach_drift - current_drift)
            
            if drift_diff > max_opposing_drift:
                max_opposing_drift = drift_diff
                best_counterparty = cname

        if best_counterparty is None:
            logging.warning(f"No counterparty found for breach at {target.now}. Skipping rebalance.")
            return False

        # 3. MODIFY TARGETS: Freeze all assets except the two traders
        new_targets = {}
        for cname in targets.keys():
            if cname == breached_asset or cname == best_counterparty:
                # Keep the original target weights for these two
                new_targets[cname] = targets[cname]
            elif cname in target.children:
                # Set target to current weight so no trade occurs
                new_targets[cname] = target.children[cname].weight
            else:
                new_targets[cname] = 0

        # Update the temp weights for the Rebalance() algo
        target.temp['weights'] = new_targets
        
        # print(f"TWO-TRADE REBALANCE | {target.now:%Y-%m-%d} | {breached_asset} <-> {best_counterparty}")
        return True

def portfolio_backtest(df_portfolios, asset_prices, assets_meta_df):
    backtests = []

    for name in df_portfolios.columns:

        rb_run, rb_type = get_rebalance_settings(name, df_portfolios)
        rb_run_algo = parse_rb_run(name, rb_run)
        rb_type_algo = parse_rb_type(name, rb_type, assets_meta_df)

        # Drop setting rows (they start with double underscore)
        weights_series = df_portfolios[name].dropna()
        weights_series = weights_series[~weights_series.index.str.startswith('__')]

        # Extract and clean weights
        weights_series = weights_series[weights_series > 0]
        weights = {str(k): v for k, v in weights_series.to_dict().items()}

        print(f"Backtesting {name} using {rb_run_algo.name}, {getattr(rb_type_algo, 'name', 'None')}")

        # Create the list of algos
        algos = [
            rb_run_algo,
            bt.algos.SelectAll(),
            bt.algos.WeighSpecified(**weights),
            rb_type_algo,  # This could be None
            bt.algos.Rebalance()
        ]

        # Remove None values from the list
        algos = [a for a in algos if a is not None]

        # Strategy setup
        strategy = bt.Strategy(name, algos)
    
        backtests.append(bt.Backtest(strategy, asset_prices, initial_capital=1e12))

    return bt.run(*backtests)

def parse_rb_type(name, rb_type, assets_meta_df):

    if 'sigma' == rb_type:
        rb_type_algo = TwoTradeRangeRebalancer(assets_meta_df)
    else:
        print(f"{name} has unknown rebalance type setting '{rb_type}', defaulting to None")
        rb_type_algo = None

    return rb_type_algo

def parse_rb_run(name, rb_run):

    if 'semi-annual' == rb_run or 'half-year' == rb_run:
        run_algo = RunSemiAnnually()
    elif 'monthly' == rb_run:
        run_algo = bt.algos.RunMonthly()
    elif 'daily' == rb_run:
        run_algo = bt.algos.RunDaily()
    elif 'yearly' == rb_run:
        run_algo = bt.algos.RunYearly()
    else:
        print(f"{name} has unknown rebalance run setting '{rb_run}', defaulting to RunOnce")
        run_algo = bt.algos.RunOnce()

    return run_algo


def get_rebalance_settings(name, df_portfolios):

    if '__rb_run' in df_portfolios.index:
        strat_row = df_portfolios.loc['__rb_run']
        rb_run = str(strat_row[name]).lower().strip()
    else:
        rb_run = None

    if '__rb_type' in df_portfolios.index:
        strat_row = df_portfolios.loc['__rb_type']
        rb_type = str(strat_row[name]).lower().strip()
    else:
        rb_type = None

    return rb_run, rb_type

