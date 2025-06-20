import streamlit as st
import sqlite3
import random
from datetime import datetime
import requests
import time

def get_llm_explanation(goal, room, loyalty_tier, upsell_room=None, price_diff=None):
    API_URL = "https://router.huggingface.co/featherless-ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {st.secrets['hf_api_key']}",
        "Content-Type": "application/json"
    }

    if upsell_room:
        content = (
            f"A guest with goal '{goal}' and loyalty tier '{loyalty_tier}' is being recommended a '{room}' room. "
            f"Explain why this is a good match. Also suggest what additional experience they could get by upgrading "
            f"to a '{upsell_room}' room for ${price_diff:.2f} more."
        )
    else:
        content = (
            f"A guest with goal '{goal}' and loyalty tier '{loyalty_tier}' is being recommended a '{room}' room. "
            f"Explain why this room suits their needs."
        )

    payload = {
        "model": "mistralai/Magistral-Small-2506",
        "messages": [{"role": "user", "content": content}]
    }

    max_retries = 3
    backoff_seconds = 2

    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=20)
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (attempt + 1))  # Exponential backoff
            else:
                # Friendly fallback explanation
                if upsell_room:
                    return (
                        f"Upgrading from {room} to {upsell_room} gives you more comfort and amenities "
                        f"for just a bit more money (${price_diff:.2f} extra). This upgrade is recommended "
                        f"for guests looking for a premium experience."
                    )
                else:
                    return (
                        f"The {room} room is a great choice for guests with goal '{goal}' "
                        f"and loyalty tier '{loyalty_tier}', offering comfort and value."
                    )

@st.cache_data(show_spinner="🤖 Generating explanation...")
def get_llm_explanation_cached(goal, room, loyalty_tier, upsell_room, price_diff):
    return get_llm_explanation(goal, room, loyalty_tier, upsell_room, price_diff)

def find_upsell_option(current_room):
    room_order = ["Standard", "Deluxe", "Suite", "Executive Suite"]
    try:
        idx = room_order.index(current_room)
        if idx < len(room_order) - 1:
            return room_order[idx + 1]
    except ValueError:
        pass
    return None

def get_recommendations(goal, loyalty_tier, preferred_room):
    conn = sqlite3.connect("hotel_data.db")
    cursor = conn.cursor()

    # Try exact match
    cursor.execute("""
        SELECT preferred_room, final_price, loyalty_discount, loyalty_tier
        FROM loyalty_bookings
        WHERE preferred_room = ? AND loyalty_tier = ?
        ORDER BY booking_date DESC
        LIMIT 1
    """, (preferred_room, loyalty_tier))
    exact_match = cursor.fetchall()

    if exact_match:
        conn.close()
        return exact_match, False  # False = fallback not used

    # Fallback: Top 3 by goal
    cursor.execute("""
        SELECT preferred_room, final_price, loyalty_discount, loyalty_tier
        FROM loyalty_bookings
        WHERE goal = ?
        ORDER BY booking_date DESC
        LIMIT 3
    """, (goal,))
    fallback_matches = cursor.fetchall()
    conn.close()
    return fallback_matches, True


def reset_session():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["secret_number"] = random.randint(1, 10)



def main():
    st.title("🏨 Smart Concierge Agent")

    if "finalized" not in st.session_state:
        st.session_state["finalized"] = False

    if st.session_state["finalized"]:
        st.success(f"✅ Your final price is ${st.session_state['final_price']:.2f}.")
        st.markdown("### 📧 Please proceed to confirm your booking")
        if st.button("📨 Proceed"):
            st.markdown("Thank you for booking with us! We'll reach out shortly. 💌")
            st.markdown("👉 [Email us](mailto:info@hotels.com) if you need anything else.")
        if st.button("🔄 Search Again"):
            reset_session()
            st.rerun()
        return

    guest_name = st.text_input("Enter your name:", disabled=st.session_state.get("recommendation_ready", False))
    goal = st.selectbox("Your travel goal:", ["relax", "explore", "work"], disabled=st.session_state.get("recommendation_ready", False))
    loyalty_tier = st.selectbox("Your loyalty tier:", ["None", "Bronze", "Silver", "Gold", "Platinum"], disabled=st.session_state.get("recommendation_ready", False))
    preferred_room = st.selectbox("Preferred room type:", ["Standard", "Deluxe", "Suite", "Executive Suite"], disabled=st.session_state.get("recommendation_ready", False))

    if st.button("Get Recommendation"):
        if not guest_name:
            st.warning("Please enter your name.")
            return
        results, fallback = get_recommendations(goal, loyalty_tier, preferred_room)
        if results:
            st.session_state.update({
                "results": results,
                "fallback": fallback,
                "recommendation_ready": True,
                "guest_name": guest_name,
                "goal": goal,
                "loyalty_tier": loyalty_tier,
                "preferred_room": preferred_room
            })
            st.rerun()
        else:
            st.error("Sorry, no recommendations available.")
            return


    if st.session_state.get("recommendation_ready"):
        st.subheader("🛎️ Your Booking Recommendation")

        results = st.session_state["results"]
        fallback = st.session_state["fallback"]

        if fallback:
            st.info("No exact match found. Here are your top 3 suggestions:")
            for i, (room, rate, discount, tier) in enumerate(results, 1):
                st.markdown(f"**Option {i}:** {room} — ${rate:.2f} (Tier: {tier}, Discount: {discount}%)")
                explanation = get_llm_explanation_cached(goal, room, loyalty_tier, None, None)
                st.markdown(f"**🤖 Why Option {i} Might Work:**")
                st.info(explanation)
            if "choice_made" not in st.session_state:
                option_choice = st.radio("Select your preferred option:", options=[1,2,3], index=0)
                if st.button("Confirm Choice"):
                    chosen = results[option_choice-1]
                    room = chosen[0]
                    rate = chosen[1]
                    st.session_state["chosen_room"] = room
                    st.session_state["final_price"] = rate
                    st.session_state["original_price"] = rate
                    st.session_state["choice_made"] = True
                    st.rerun()
            else:
                st.success(f"You selected option with {st.session_state['chosen_room']} room at ${st.session_state['final_price']:.2f}")
            

        else:
            room, rate, discount, tier = results[0]
            st.success(f"{room} room at ${rate:.2f} (Tier: {tier}, Discount: {discount}%)")
            if "final_price" not in st.session_state:
                st.session_state["final_price"] = rate  # or whatever initial price

            st.session_state["original_price"] = rate
                    # Show LLM explanation for exact match
            explanation = get_llm_explanation_cached(goal, room, loyalty_tier, None, None)
          
            if explanation.startswith("🤖 Could not generate explanation"):
                st.warning("⚠️ Sorry, the AI explanation service is temporarily unavailable. You can still book with confidence!")
            else:
                st.markdown("### 🤖 Why This Room?")
                st.info(explanation)


            # Try to upsell
            conn = sqlite3.connect("hotel_data.db")
            upsell_room = find_upsell_option(room)

            if upsell_room:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT final_price FROM loyalty_bookings
                    WHERE preferred_room = ? AND loyalty_tier = ?
                    ORDER BY booking_date DESC LIMIT 1
                """, (upsell_room, loyalty_tier))
                upsell_result = cursor.fetchone()


                conn.close()
                if upsell_result:
                    upsell_price = upsell_result[0]
                    price_diff = upsell_price - rate
                    if price_diff > 0:
                        upsell_explanation = get_llm_explanation_cached(goal, room, loyalty_tier, upsell_room, price_diff)
                        st.markdown("### 💎 Want to Upgrade?")
                        st.success(f"For just ${price_diff:.2f} more, upgrade to a {upsell_room} room.")
                        st.info(upsell_explanation)

                        if "choice_made" not in st.session_state:
                            upgrade_choice = st.radio("Choose your option:", [f"Keep {room} room", f"Upgrade to {upsell_room} room (+${price_diff:.2f})"])
                            if st.button("Confirm Choice"):
                                if upgrade_choice.startswith("Keep"):
                                    st.session_state["chosen_room"] = room
                                    st.session_state["final_price"] = rate
                                    st.session_state["original_price"] = rate
                                else:
                                    st.session_state["chosen_room"] = upsell_room
                                    st.session_state["final_price"] = upsell_price
                                    st.session_state["original_price"] = upsell_price
                                st.session_state["choice_made"] = True
                                st.rerun()
                        else:
                            st.success(f"You selected {st.session_state['chosen_room']} room at ${st.session_state['final_price']:.2f}")
                    else:
                        # No upsell available, auto choose current
                        st.session_state["chosen_room"] = room
                        st.session_state["final_price"] = rate
                        st.session_state["original_price"] = rate
                        st.session_state["choice_made"] = True
                else:
                    # No upsell, auto select current
                    st.session_state["chosen_room"] = room
                    st.session_state["final_price"] = rate
                    st.session_state["original_price"] = rate
                    st.session_state["choice_made"] = True
                    


        if st.session_state.get("choice_made"):
            st.divider()
            st.subheader("🎲 Try Your Luck for a 5% Extra Discount")

            


            if "used_luck" not in st.session_state:
                st.session_state["used_luck"] = False
                st.session_state["got_lucky"] = False

            if not st.session_state["used_luck"]:
                if "secret_number" not in st.session_state:
                    st.session_state["secret_number"] = random.randint(1, 10)
                lucky_guess = st.number_input("Pick a number between 1 and 10:", min_value=1, max_value=10, step=1)

                

                st.write("🔐 Secret Number (for testing):", st.session_state["secret_number"])

                if st.button("Try Your Luck"):
                    if lucky_guess == st.session_state["secret_number"]:
                        # Calculate discount based on original price
                        discount_price = round(st.session_state["original_price"] * 0.95, 2)
                        st.session_state["final_price"] = discount_price
                        st.session_state["got_lucky"] = True
                        st.success(f"🎉 You guessed correctly! New discounted price: ${discount_price:.2f}")
                    else:
                        st.session_state["got_lucky"] = False
                        st.error("❌ Sorry, wrong guess. Better luck next time!")
                    st.session_state["used_luck"] = True
                    st.rerun()
            else:
                # Always show the current final_price from session state
                if st.session_state.get("got_lucky"):
                    st.success(f"🎉 Your discounted final price: ${st.session_state['final_price']:.2f}")
                else:
                    st.info(f"Your final price remains: ${st.session_state['final_price']:.2f}")

            if st.button("📨 Proceed"):
                st.session_state["finalized"] = True
                st.rerun()

            # Debug prints to check values persistency (remove after testing)








if __name__ == "__main__":
    main()
