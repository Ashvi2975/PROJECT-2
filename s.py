"""
WORLD FRAUD ENGINE — ALBERTA PRIORITY (ADVANCED TD-STYLE VERSION)
Author: Ashvi

Features:
- Alberta city verification
- Worldwide province + country validation (pycountry)
- Unknown locations = extra risk (NOT instant block)
- Auto-approve for small amounts (< $150)
- Amount ZONES for verification:
    - $150–1000: normal checks (no forced verification unless risk high)
    - >$1000: PIN
    - >$2000: PIN + ONE (Last name / DOB / CCV)
    - >$5000: FULL (Last name + DOB + CCV + PIN)
- Time-of-day risk (late-night transactions riskier)
- Merchant category risk (groceries vs gift cards, etc.)
- Velocity risk (transactions too close together)
- Location jump risk (jumping from AB to another region)
- Behavioural risk (compared to past spending patterns)
- PIN + identity verification system with escalating responses
- 5 flagged events = CARD FROZEN
- Verification failures:
    - 3 fails → warning, no freeze yet
    - 5 fails → freeze
    - 7 fails → block
- NO REAL DATA — all identity info is fictional placeholders
"""

import pycountry
import statistics
from datetime import datetime, timedelta

AVERAGE_SPEND = 500
CORRECT_PIN = "1234"          # Fictional, for simulation only

# Fictional identity details for verification simulation
SIM_LAST_NAME = "Wahdan"
SIM_DOB = "1990-05-14"        # YYYY-MM-DD, fake
SIM_CVV = "123"               # Fake CVV

# Alberta cities (for “local” profile)
ALBERTA_CITIES = {
    "calgary", "edmonton", "red deer", "lethbridge", "medicine hat",
    "airdrie", "st. albert", "fort mcmurray", "grand prairie", "okotoks",
    "cochrane", "spruce grove", "camrose", "brooks", "banff", "canmore"
}

WORLD_PROVINCES = {s.name.lower(): s.code for s in pycountry.subdivisions}
WORLD_COUNTRIES = {c.name.lower(): c.alpha_2 for c in pycountry.countries}

# Merchant categories + base risk
MERCHANT_RISK = {
    "1": ("Groceries / Essentials", 0.00),
    "2": ("Restaurants / Food", 0.05),
    "3": ("Electronics / Tech", 0.10),
    "4": ("Travel / Airline / Hotel", 0.15),
    "5": ("Online / E-commerce / Marketplace", 0.20),
    "6": ("Gift Cards / Crypto / Reloadables", 0.30),
    "7": ("Other / Misc", 0.05),
}

# Spending pattern history
spending_history = []  # list of dicts: {"amount", "merchant", "hour", "region"}


# ========== LOCATION VALIDATION ==========

def validate_location(location: str):
    location = location.lower().strip()
    parts = location.split(",")

    if len(parts) != 2:
        return None, False, "Invalid format. Use: City, Region."

    city = parts[0].strip()
    region = parts[1].strip()

    # Alberta priority
    if city in ALBERTA_CITIES and region == "ab":
        return "ab", True, "Valid Alberta location"

    if region in WORLD_PROVINCES:
        return region, True, "Valid world subdivision/state"

    if region in WORLD_COUNTRIES:
        return region, True, "Valid world country"

    return None, False, "Unknown location (not in global database)"


# ========== RISK COMPONENTS ==========

def add_amount_zone_risk(amount, reasons):
    if amount <= 500:
        return 0.0
    elif amount <= 2000:
        reasons.append("Caution spend zone ($501–$2,000)")
        return 0.10
    elif amount <= 5000:
        reasons.append("Risk spend zone ($2,001–$5,000)")
        return 0.20
    elif amount <= 10000:
        reasons.append("High-risk spend zone ($5,001–$10,000)")
        return 0.30
    elif amount <= 20000:
        reasons.append("Severe spend zone ($10,001–$20,000)")
        return 0.40
    else:
        reasons.append("Critical spend zone (>$20,000)")
        return 0.50


def add_location_risk(region, reasons):
    if region != "ab":
        reasons.append("Transaction outside normal Alberta activity zone")
        return 0.30
    return 0.0


def add_unknown_location_risk(known_location, reasons):
    if not known_location:
        reasons.append("Unknown / unverified location")
        return 0.10
    return 0.0


def add_time_of_day_risk(now, reasons):
    # Late night 00:00 – 05:00 = risk
    if 0 <= now.hour < 5:
        reasons.append("Late-night transaction (00:00–05:00)")
        return 0.10
    return 0.0


def add_merchant_risk(merchant_choice, reasons):
    label, risk = MERCHANT_RISK.get(merchant_choice, MERCHANT_RISK["7"])
    reasons.append(f"Merchant category: {label}")
    return risk


def add_velocity_risk(last_tx_time, now, reasons):
    if last_tx_time is None:
        return 0.0
    if (now - last_tx_time) <= timedelta(seconds=60):
        reasons.append("High transaction velocity (within 60 seconds)")
        return 0.15
    return 0.0


def add_location_jump_risk(last_region, region, reasons):
    if last_region is None:
        return 0.0
    if (region or "unknown") != (last_region or "unknown"):
        reasons.append("Sudden change in transaction region")
        return 0.10
    return 0.0


# ========== SPENDING PATTERN ANALYSIS ==========

def analyze_spending_patterns():
    # Need at least a bit of history to make sense
    if len(spending_history) < 5:
        return None

    amounts = [tx["amount"] for tx in spending_history]
    merchants = [tx["merchant"] for tx in spending_history]
    hours = [tx["hour"] for tx in spending_history]
    regions = [tx["region"] for tx in spending_history]

    avg_amount = sum(amounts) / len(amounts)

    frequent_merchant = max(set(merchants), key=merchants.count)
    avg_hour = sum(hours) / len(hours)
    frequent_region = max(set(regions), key=regions.count)

    return {
        "avg_amount": avg_amount,
        "frequent_merchant": frequent_merchant,
        "avg_hour": avg_hour,
        "frequent_region": frequent_region
    }


def add_behavioral_risk(amount, merchant_label, now, region, reasons):
    patterns = analyze_spending_patterns()
    if not patterns:
        return 0.0

    risk = 0.0

    # Amount vs normal
    if amount > patterns["avg_amount"] * 3:
        reasons.append(
            f"Unusually high amount vs normal (${patterns['avg_amount']:.2f} avg)"
        )
        risk += 0.20

    # Merchant vs usual
    if merchant_label != patterns["frequent_merchant"]:
        reasons.append(
            f"Merchant differs from usual ({patterns['frequent_merchant']})"
        )
        risk += 0.10

    # Time vs usual
    if abs(now.hour - patterns["avg_hour"]) > 6:
        reasons.append("Transaction time unusual vs typical behaviour")
        risk += 0.10

    # Region vs usual
    if region != patterns["frequent_region"]:
        reasons.append(
            f"Region unusual — typical region: {patterns['frequent_region']}"
        )
        risk += 0.10

    return risk


# ========== DECISION / OUTPUT ==========

def decide(risk):
    if risk < 0.50:
        return "APPROVED"
    elif 0.50 <= risk <= 0.80:
        return "APPROVED (FLAGGED)"
    elif 0.80 < risk <= 0.90:
        return "CALL BANK (Verification Recommended)"
    elif 0.90 < risk < 1.0:
        return "CARD UNDER REVIEW (High Risk)"
    else:
        return "CRITICAL RISK (Manual Review Needed)"


def print_block_instructions(block_type):
    print("\n----------------------------------------------")
    if block_type == "frozen":
        print("❌ CARD FROZEN — Too many suspicious events.")
        print("Steps:")
        print("1. Contact your bank using the official number.")
        print("2. Verify your identity and review recent activity.")
        print("3. A new card may be issued.")
    else:
        print("❌ CARD PERMANENTLY BLOCKED — Maximum risk reached.")
        print("Steps:")
        print("1. Contact your bank's fraud department immediately.")
        print("2. Your account may be locked for your protection.")
        print("3. A new card will be issued to you.")
    print("----------------------------------------------\n")


# ========== VERIFICATION SYSTEM ==========

def run_verification(amount, risk):
    """
    Tiered verification:
    - Amount < 1000 & risk < 0.50 → no verification from here (will not be called)
    - >1000 or risk >= 0.50 triggers different levels:
        >5000 OR risk >= 0.90 → full verification
        >2000 OR risk >= 0.70 → PIN + ONE (last / dob / cvv)
        >1000 OR risk >= 0.50 → PIN only
    """
    print("\n⚠️ Verification Required — Suspicious / High-Value Activity Detected")

    # Decide verification tier
    full_check = (amount > 5000) or (risk >= 0.90)
    mid_check = (amount > 2000) or (risk >= 0.70)
    pin_only = (amount > 1000) or (risk >= 0.50)

    # FULL VERIFICATION
    if full_check:
        print("Tier: 🔴 FULL VERIFICATION (Last name + DOB + CVV + PIN)")

        last = input("Enter your last name: ").strip().lower()
        if last != SIM_LAST_NAME.lower():
            print("❌ Verification failed: last name mismatch.")
            return False

        dob = input("Enter your date of birth (YYYY-MM-DD): ").strip()
        if dob != SIM_DOB:
            print("❌ Verification failed: birthdate mismatch.")
            return False

        cvv = input("Enter your 3-digit CVV: ").strip()
        if cvv != SIM_CVV:
            print("❌ Verification failed: CVV mismatch.")
            return False

        pin = input("Enter your 4-digit PIN: ").strip()
        if pin != CORRECT_PIN:
            print("❌ Verification failed: PIN incorrect.")
            return False

        print("✅ Verification passed.")
        return True

    # MID TIER: PIN + ONE QUESTION
    if mid_check:
        print("Tier: 🟠 PIN + ONE of Last Name / DOB / CVV")

        pin = input("Enter your 4-digit PIN: ").strip()
        if pin != CORRECT_PIN:
            print("❌ Verification failed: PIN incorrect.")
            return False

        print("\nChoose one verification option:")
        print("1) Last Name\n2) Date of Birth\n3) CVV")
        choice = input("Select (1–3): ").strip()

        if choice == "1":
            last = input("Enter your last name: ").strip().lower()
            if last != SIM_LAST_NAME.lower():
                print("❌ Verification failed: last name mismatch.")
                return False

        elif choice == "2":
            dob = input("Enter your date of birth (YYYY-MM-DD): ").strip()
            if dob != SIM_DOB:
                print("❌ Verification failed: birthdate mismatch.")
                return False

        elif choice == "3":
            cvv = input("Enter your 3-digit CVV: ").strip()
            if cvv != SIM_CVV:
                print("❌ Verification failed: CVV mismatch.")
                return False

        else:
            print("❌ Invalid verification choice.")
            return False

        print("✅ Verification passed.")
        return True

    # PIN ONLY TIER
    if pin_only:
        print("Tier: 🟡 PIN ONLY")
        pin = input("Enter your 4-digit PIN: ").strip()
        if pin != CORRECT_PIN:
            print("❌ Verification failed: PIN incorrect.")
            return False
        print("✅ Verification passed.")
        return True

    # If somehow called with no tier
    return True


# ========== MAIN LOOP ==========

def main():
    flagged_count = 0
    pin_fails = 0
    card_blocked = False
    session_log = []

    last_tx_time = None
    last_region = None

    print("\n=== WORLD FRAUD ENGINE — ADVANCED TD-STYLE VERSION ===\n")

    while True:
        if card_blocked:
            break

        print("\n--- New Transaction ---")

        # SAFE AMOUNT INPUT
        while True:
            amt_input = input("Enter amount ($): ")
            try:
                amount = float(amt_input)
                if amount > 0:
                    break
                print("❌ Amount must be positive.")
            except:
                print("❌ Invalid input. Enter a number.")

        now = datetime.now()

        # QUICK AUTO-APPROVAL FOR SMALL AMOUNTS
        if amount < 150:
            print("\n=== FRAUD RESULT ===")
            print("Risk Score: 0.00")
            print("Decision:   APPROVED")
            print("\nReasons:")
            print(" • Low-value transaction (< $150) auto-approved.")

            # Log small transaction (minimal info)
            session_log.append({
                "risk": 0.0,
                "decision": "APPROVED (Low-value auto-approve)"
            })
            spending_history.append({
                "amount": amount,
                "merchant": "Low-Value Auto-Approved",
                "hour": now.hour,
                "region": "ab"
            })
            last_tx_time = now
            last_region = "ab"
            again = input("\nAnalyze another transaction? (yes/no): ").lower()
            if again != "yes":
                break
            else:
                continue

        # LOCATION INPUT
        location = input("Enter location (City, Region/Country): ")
        region, known_location, loc_reason = validate_location(location)

        # MERCHANT TYPE
        print("\nMerchant Type:")
        print("1) Groceries\n2) Restaurants\n3) Electronics\n4) Travel\n5) Online\n6) Gift Cards\n7) Other")
        choice = input("Choose (1–7): ").strip()
        if choice not in MERCHANT_RISK:
            choice = "7"
        merchant_label, _ = MERCHANT_RISK[choice]

        reasons = []

        # RISK CALCULATION
        risk = 0.0
        risk += add_amount_zone_risk(amount, reasons)
        risk += add_location_risk(region, reasons)
        risk += add_unknown_location_risk(known_location, reasons)
        risk += add_time_of_day_risk(now, reasons)
        risk += add_merchant_risk(choice, reasons)
        risk += add_velocity_risk(last_tx_time, now, reasons)
        risk += add_location_jump_risk(last_region, region, reasons)
        risk += add_behavioral_risk(amount, merchant_label, now, region or "unknown", reasons)

        # Location message
        reasons.append(loc_reason)

        risk = min(risk, 1.0)
        decision = decide(risk)

        # VERIFICATION LOGIC:
        # - Any amount > 1000
        # - OR any amount >= 150 with risk >= 0.50
        verification_required = (amount > 1000) or (risk >= 0.50)

        if verification_required:
            print(f"\n⚠️ Risk-based / amount-based verification triggered (Risk = {risk:.2f}, Amount = ${amount:.2f})")
            verified = run_verification(amount, risk)

            if not verified:
                pin_fails += 1
                flagged_count += 1
                reasons.append("Verification failed; transaction declined.")

                print("\n=== FRAUD RESULT ===")
                print(f"Risk Score: {risk:.2f}")
                print("Decision:   DECLINED (Failed Verification)")
                print("\nReasons:")
                for r in reasons:
                    print(" •", r)

                session_log.append({
                    "risk": round(risk, 2),
                    "decision": "DECLINED (Failed Verification)"
                })

                # Escalation based on failed attempts
                if pin_fails == 3:
                    print("\n⚠️ Multiple failed attempts (3). Further verification will be stricter.")
                elif pin_fails == 5:
                    print_block_instructions("frozen")
                    card_blocked = True
                    break
                elif pin_fails >= 7:
                    print_block_instructions("blocked")
                    card_blocked = True
                    break

                # Move to next transaction
                again = input("\nAnalyze another transaction? (yes/no): ").lower()
                if again != "yes":
                    break
                else:
                    last_tx_time = now
                    last_region = region or "unknown"
                    continue
            else:
                # Successful verification resets PIN fail counter
                pin_fails = 0
                reasons.append("Verification passed successfully.")

        # FINAL DECISION OUTPUT (no auto-block from decision alone)
        print("\n=== FRAUD RESULT ===")
        print(f"Risk Score: {risk:.2f}")
        print(f"Decision:   {decision}")
        print("\nReasons:")
        for r in reasons:
            print(" •", r)

        # Update state
        last_tx_time = now
        last_region = region or "unknown"

        spending_history.append({
            "amount": amount,
            "merchant": merchant_label,
            "hour": now.hour,
            "region": region or "unknown"
        })

        if decision != "APPROVED":
            flagged_count += 1

        # Flag-based freeze
        if flagged_count >= 5:
            print_block_instructions("frozen")
            card_blocked = True
            break

        again = input("\nAnalyze another transaction? (yes/no): ").lower()
        if again != "yes":
            break

    # SESSION SUMMARY
    print("\n=========== SESSION SUMMARY ===========")
    for i, t in enumerate(session_log, 1):
        print(f"{i}. Risk = {t['risk']} — {t['decision']}")
    print("========================================")

    if card_blocked:
        print("FINAL STATUS: ❌ Card Blocked/Frozen\n")
    else:
        print("FINAL STATUS: ✅ Card Active\n")

    # SPENDING PATTERN SUMMARY
    patterns = analyze_spending_patterns()
    if patterns:
        print("====== 🌈 SPENDING PATTERN SUMMARY 🌈 ======")
        print(f"💵 Average Spend:          ${patterns['avg_amount']:.2f}")
        print(f"🛍️ Common Merchant Type:  {patterns['frequent_merchant']}")
        print(f"🕒 Usual Transaction Hour: Around {int(patterns['avg_hour'])}:00")
        print(f"📍 Main Region Used:       {patterns['frequent_region'].upper()}")
        print("================================================")


if __name__ == "__main__":
    main()
