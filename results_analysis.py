
from collections import namedtuple
from collections import defaultdict
import datetime
import json
import pytz

import numpy


RESULTS_FILE = 'results'
ANALYSIS_FILE = 'analysis.json'
TREASURY_MONTHLY_YIELD = 0.12

# eval() generated
Position = namedtuple(
    'Position',
    (
        'open_bsi open_price open_timestamp '
        'close_bsi close_price close_timestamp '
        'profit'
    )
)
EnrichedPosition = namedtuple(
    'EnrichedPosition',
    Position._fields + (
        'symbol',
        'std_dev',
        'open_datetime',
        'close_datetime'
    )
)


def _calc_monthly_profits(positions):
    results = []

    curr_month = positions[0].open_datetime.month
    curr_result = 0.0
    for position in positions:
        month = position.open_datetime.month
        if month != curr_month:
            results.append(curr_result)
            curr_month = month
            curr_result = position.profit
        else: 
            curr_result += position.profit

    results.append(curr_result)
    return results


def _utc_ts_to_et_dt(ts):
    naive_dt = datetime.datetime.utcfromtimestamp(ts)
    utc_dt = pytz.timezone('UTC').localize(naive_dt)
    return utc_dt.astimezone(pytz.timezone('US/Eastern'))


def _generate_symbol_data(positions):
    traded_days = set()

    symbol_to_profit = defaultdict(int)
    symbol_to_exec_n = defaultdict(int)
    symbol_to_exec_avg_n = {}

    for position in positions:
        time = position.open_datetime
        day = (time.day, time.month, time.year)
        traded_days.add(day)

        symbol = position.symbol
        profit = position.profit

        symbol_to_profit[symbol] += float(profit)
        symbol_to_exec_n[symbol] += 1

    traded_days_n = len(traded_days)
    
    for symbol, exec_n in symbol_to_exec_n.items():
        symbol_to_exec_avg_n[symbol] = exec_n / traded_days_n
    
    return dict(
        symbol_to_profit=symbol_to_profit,
        symbol_to_exec_n=symbol_to_exec_n,
        symbol_to_exec_avg_n=symbol_to_exec_avg_n
    )


def _generate_analysis(all_positions):
    # general
    traded_days = len(
        set(
            [
                (
                    p.open_datetime.day,
                    p.open_datetime.month,
                    p.open_datetime.year
                ) for
                p in
                all_positions
            ]
        )
    )
    exec_n = len(all_positions) * 2
    symbols_n = len(
        set([p.symbol for p in all_positions])
    )
    avg_trades_per_day = exec_n / traded_days
    avg_trades_per_day_per_symbol = symbols_n / avg_trades_per_day

    # winning trades
    winning_trades = [p for p in all_positions if p.profit > 0.0]
    won_n = len(winning_trades)
    total_won = sum([p.profit for p in winning_trades])
    average_win = total_won / won_n

    # losing trades
    losing_trades = [p for p in all_positions if p.profit < 0.0]
    lost_n = len(losing_trades)
    total_lost = sum([p.profit for p in losing_trades])
    average_loss = total_lost / lost_n

    # sharpe ratio
    monthly_profits = _calc_monthly_profits(all_positions)
    excess_profits = [p - TREASURY_MONTHLY_YIELD for p in monthly_profits]
    excess_std_dev = numpy.std(excess_profits)
    excess_average = sum(excess_profits) / len(excess_profits)
    sharpe_ratio = excess_average / excess_std_dev

    return dict(
        general=dict(
            start=str(all_positions[0].open_datetime.date()),
            end=str(all_positions[-1].close_datetime.date()),
            symbols_n=symbols_n,
            days_n=traded_days,
            profit=sum(monthly_profits),
            exec_n=len(all_positions) * 2,
            daily_exec_n=avg_trades_per_day,
            daily_exec_symbol_n=avg_trades_per_day_per_symbol
        ),
        winning_trades=dict(
            total_won=total_won,
            won_n=won_n,
            average_win=average_win
        ),
        losing_trades=dict(
            total_lost=total_lost,
            lost_n=lost_n,
            average_loss=average_loss
        ),
        sharpe_ratio=dict(
            us10y_monthly_yield=TREASURY_MONTHLY_YIELD,
            excess_average=excess_average,
            excess_std_dev=excess_std_dev,
            sharpe_ratio=sharpe_ratio
        ),
        symbol_data=_generate_symbol_data(all_positions)
    )


def _print_analysis(analysis):
    symbol_data = analysis['symbol_data']
    symbol_to_profit = symbol_data['symbol_to_profit']
    symbol_to_exec_n = symbol_data['symbol_to_exec_n']
    symbol_to_exec_avg_n = symbol_data['symbol_to_exec_avg_n']

    symbol_analysis_string = "\n".join([
        (
            f"\t{symbol}:\n"
            f"\t\tprofit: {round(symbol_to_profit[symbol], 3)}\n"
            f"\t\texec_n: {symbol_to_exec_n[symbol]}\n"
            f"\t\tdaily_n: {round(symbol_to_exec_avg_n[symbol], 3)}"
        )
        for symbol in
        sorted(
            list(symbol_to_profit.keys()),
            key=lambda s: symbol_to_profit[s],
            reverse=True
        )
    ])

    general = analysis['general']
    winning_trades = analysis['winning_trades']
    losing_trades = analysis['losing_trades']
    sharpe_ratio = analysis['sharpe_ratio']

    print(
        (
            f"\ngeneral data:\n"
            f"\tstart: {general['start']}\n"
            f"\tend: {general['end']}\n"
            f"\ttraded symbols: {general['symbols_n']}\n"
            f"\ttraded days: {general['days_n']}\n"
            f"\tprofit: {round(general['profit'], 3)}\n"
            f"\tnumber of executions: {general['exec_n']}\n"
            f"\taverage daily number of executions: {round(general['daily_exec_n'])}\n"
            f"\taverage daily number of executions per symbol: {round(general['daily_exec_symbol_n'], 3)}\n\n"
            f"winning trades:\n"
            f"\tsum: {round(winning_trades['total_won'], 3)}\n"
            f"\tn: {winning_trades['won_n']}\n"
            f"\taverage: {round(winning_trades['average_win'], 3)}\n\n"
            f"losing trades:\n"
            f"\tsum: {round(losing_trades['total_lost'], 3)}\n"
            f"\tn: {losing_trades['lost_n']}\n"
            f"\taverage: {round(losing_trades['average_loss'], 3)}\n\n"
            f"sharpe ratio:\n"
            f"\tUS10Y monthly yield: {sharpe_ratio['us10y_monthly_yield']}\n"
            f"\texcess profits average: {round(sharpe_ratio['excess_average'], 3)}\n"
            f"\texcess profits std dev: {round(sharpe_ratio['excess_std_dev'], 3)}\n"
            f"\tsharpe ratio: {round(sharpe_ratio['excess_average'], 3)} / {round(sharpe_ratio['excess_std_dev'], 3)} = "
            f"{round(sharpe_ratio['sharpe_ratio'], 3)}\n\n"
            f"symbol data:\n{symbol_analysis_string}\n"
        )
    )


def main():
    with open(RESULTS_FILE) as f:
        results = [
            eval(result.strip()) for
            result in
            f.readlines()
        ]

    all_positions = []
    for result in results:
        for position in result['positions']:
            all_positions.append(
                EnrichedPosition(
                    *position,
                    result['symbol'],
                    result['std_dev'],
                    _utc_ts_to_et_dt(position.open_timestamp),
                    _utc_ts_to_et_dt(position.close_timestamp)
                )
            )

    all_positions.sort(key=lambda pos: pos.open_datetime)

    analysis = _generate_analysis(all_positions)
    with open(ANALYSIS_FILE, 'w') as f:
        json.dump(analysis, f, indent=4)

    _print_analysis(analysis)


if __name__ == '__main__':
    main()
