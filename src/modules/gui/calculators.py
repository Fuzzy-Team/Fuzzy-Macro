"""Pure ports of the calculators in webapp/scripts/tabs/tools.js.

Float arithmetic intentionally matches JavaScript Number, including totals
above the exact integer range. No automation or settings imports are needed.
"""

import math
import re
from decimal import Decimal, ROUND_HALF_UP, localcontext


TREAT_COST_HONEY = 10000
BOND_REQUIREMENTS = (
    0, 10, 40, 200, 750, 4000, 15000, 60000, 270000, 450000,
    1200000, 2000000, 4000000, 7000000, 15000000, 120000000,
    450000000, 1900000000, 7500000000, 15000000000, 475000000000,
    4500000000000, 95000000000000, 900000000000000, 9000000000000000,
)
TICKET_CALC_DEFAULT_NEXT_PRICE = 100000
TICKET_CALC_MAX_TICKETS = 100000
TICKET_CALC_PRESETS = (10, 100, 500)
HONEY_UNITS = ((1000, "K"), (1000000, "M"), (1000000000, "B"),
               (1000000000000, "T"), (1000000000000000, "Qd"),
               (1000000000000000000, "Qn"))


def number(value):
    """Number(value) || 0 for calculator input values."""
    if value is None or value == "":
        return 0.0
    try:
        if isinstance(value, str) and value.strip().lower().startswith(("0x", "0b", "0o")):
            return float(int(value.strip(), 0))
        result = float(value)
    except (ValueError, TypeError):
        return 0.0
    return 0.0 if math.isnan(result) else result


def parse_float(value):
    """JavaScript parseFloat, including numeric prefixes and empty inputs."""
    match = re.match(r"^[\s]*([+-]?(?:Infinity|(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?))", str(value))
    return float(match.group(1)) if match else float("nan")


def parse_int(value, default=0):
    match = re.match(r"^\s*([+-]?[0-9]+)", str(value))
    return int(match.group(1)) if match else default


def js_round(value):
    lower = math.floor(value)
    return lower + (value - lower >= 0.5)


def format_whole_number(value):
    # JS locale formatting uses Number's shortest decimal, not the exact
    # integer represented by its binary bits above 2**53.
    with localcontext() as context:
        context.prec = 40
        rounded = Decimal(str(float(js_round(float(value))))).quantize(Decimal("1"))
    return "{:,}".format(rounded)


def format_compact_honey(value):
    suffix = ""
    value = float(value)
    for threshold, unit in reversed(HONEY_UNITS):
        if abs(value) >= threshold:
            value /= threshold
            suffix = " " + unit
            break
    # Intl.NumberFormat rounds the shortest decimal representation, half up.
    with localcontext() as context:
        context.prec = 40
        rounded = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = "{:,.2f}".format(rounded).rstrip("0").rstrip(".")
    return text + suffix


def calculate_treats_for_bond(bond, bonus_percent):
    effective_bonus = max(0.0, number(bonus_percent) - 100)
    return math.ceil(float(bond) / (10 * (1 + effective_bonus / 100)))


def build_bond_breakdown_rows(start_level, end_level, bonus_percent, bee_count):
    rows = []
    for level in range(start_level, end_level):
        bond = BOND_REQUIREMENTS[level] if 0 <= level < len(BOND_REQUIREMENTS) else 0
        treats = calculate_treats_for_bond(bond, bonus_percent)
        cost = float(treats) * TREAT_COST_HONEY
        rows.append(dict(label="{} -> {}".format(level, level + 1), bond=bond,
                         treats=treats, costPerBee=cost, costForBees=cost * bee_count))
    return rows


def calculate_bond(start_level=1, end_level=25, bonus_percent=20, bee_count=50):
    """Return normalized inputs, per-level rows and the displayed totals."""
    start_level, end_level = parse_int(start_level), parse_int(end_level)
    bonus = parse_float(bonus_percent)
    bonus = 0 if math.isnan(bonus) or bonus < 0 else min(300, bonus)
    bees = min(50, max(1, parse_int(bee_count, 1)))
    warning = "Final level must be higher than initial level." if start_level >= end_level else ""
    rows = [] if warning else build_bond_breakdown_rows(start_level, end_level, bonus, bees)
    bond = treats = cost = 0.0
    for row in rows:
        bond += row["bond"]
        treats += row["treats"]
        cost += row["costPerBee"]
    return dict(start_level=start_level, end_level=end_level, bonus_percent=bonus,
                bee_count=bees, warning=warning, rows=rows, total_bond=bond,
                total_treats=treats * bees, cost_one=cost, cost_bees=cost * bees)


def normalize_ticket_price(value, unit=1):
    multiplier = number(unit) or 1
    price = float(js_round(number(value) * multiplier / 1000)) * 1000
    return max(TICKET_CALC_DEFAULT_NEXT_PRICE, price)


def get_tickets_bought_from_next_price(next_price):
    if next_price == TICKET_CALC_DEFAULT_NEXT_PRICE:
        return 0
    if next_price < 102000:
        return 1
    scaled = float(next_price) / 1000 - 100
    exponent = 5 / 6 if next_price <= 1824000 else 10 / 17
    return math.floor(math.pow(scaled, exponent)) + 1


def get_ticket_price_after_bought(tickets_bought):
    if tickets_bought <= 0:
        return TICKET_CALC_DEFAULT_NEXT_PRICE
    if tickets_bought == 1:
        return 101000
    exponent = 6 / 5 if tickets_bought < 499 else 17 / 10
    return float(math.ceil(math.pow(tickets_bought, exponent) + 99)) * 1000


def calculate_ticket_purchase(next_price, ticket_count):
    count = math.floor(max(0, min(TICKET_CALC_MAX_TICKETS, number(ticket_count))))
    bought = get_tickets_bought_from_next_price(next_price)
    cost = final_price = 0.0
    for index in range(count):
        price = next_price if index == 0 else get_ticket_price_after_bought(bought + index)
        cost += price
        final_price = price
    return dict(ticketsAlreadyBought=bought, ticketsToBuy=count, totalCost=cost,
                averagePrice=cost / count if count else 0, finalTicketPrice=final_price,
                nextPriceAfterPurchase=get_ticket_price_after_bought(bought + count))


def calculate_tickets_for_budget(next_price, budget):
    bought = get_tickets_bought_from_next_price(next_price)
    budget = max(0, number(budget))
    cost, tickets = 0.0, 0
    while tickets < TICKET_CALC_MAX_TICKETS:
        price = next_price if tickets == 0 else get_ticket_price_after_bought(bought + tickets)
        if cost + price > budget:
            break
        cost += price
        tickets += 1
    return dict(tickets=tickets, totalCost=cost)


def calculate_tickets(next_price=100, price_unit=1000000, custom_amount=1,
                      budget=0, budget_unit=1000000):
    price = normalize_ticket_price(next_price, price_unit)
    raw_price = number(next_price) * (number(price_unit) or 1)
    count = min(TICKET_CALC_MAX_TICKETS, max(1, math.floor(number(custom_amount) or 1)))
    amounts = list(TICKET_CALC_PRESETS)
    if count not in amounts:
        amounts.append(count)
    rows = [(amount, calculate_ticket_purchase(price, amount)) for amount in amounts]
    return dict(next_price=price, custom_amount=count, rows=rows,
                budget=calculate_tickets_for_budget(price, max(0, number(budget) * (number(budget_unit) or 1))),
                warning=("Ticket prices below 100K are raised to 100K, and prices are rounded "
                         "to the nearest 1,000 honey.") if math.isfinite(raw_price) and raw_price > 0 and raw_price != price else "")
