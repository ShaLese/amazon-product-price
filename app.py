import streamlit as st
import pandas as pd
from scraper import AmazonScraper
import time
import os

# Set page config
st.set_page_config(
    page_title="Amazon Price Tracker",
    page_icon="🛍️",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stProgress > div > div > div > div {
        background-color: #ff9900;
    }
    </style>
""", unsafe_allow_html=True)

def main():
    # Header
    st.title("🛍️ Amazon Price Tracker")
    st.markdown("Track prices of your favorite Amazon products across different regions")

    # Sidebar
    with st.sidebar:
        st.header("Settings")
        region = st.selectbox(
            "Select Region",
            ["US", "UK", "DE", "FR", "IT", "ES"],
            index=0
        )
        
        st.markdown("---")
        
        # Add Product section
        with st.expander("➕ Add Products", expanded=True):
            # Multi-line text input for multiple products
            new_products = st.text_area(
                "Enter products (one per line):",
                height=150,
                help="Enter each product on a new line"
            )
            
            if st.button("Add Products"):
                if new_products.strip():
                    # Split the input by newlines and remove empty lines
                    products_to_add = [p.strip() for p in new_products.split('\n') if p.strip()]
                    
                    if products_to_add:
                        try:
                            # Read existing products
                            try:
                                df = pd.read_csv('products.csv')
                            except FileNotFoundError:
                                df = pd.DataFrame(columns=['item_name', 'item_price', 'currency', 'currency_symbol', 'item_url'])
                            
                            # Add new products
                            new_rows = pd.DataFrame({
                                'item_name': products_to_add,
                                'item_price': ['']*len(products_to_add),
                                'currency': ['']*len(products_to_add),
                                'currency_symbol': ['']*len(products_to_add),
                                'item_url': ['']*len(products_to_add)
                            })
                            df = pd.concat([df, new_rows], ignore_index=True)
                            
                            # Remove duplicates
                            df = df.drop_duplicates(subset=['item_name'], keep='first')
                            
                            # Save updated DataFrame
                            df.to_csv('products.csv', index=False)
                            st.success(f"Added {len(products_to_add)} new product(s)!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")
                    else:
                        st.warning("Please enter at least one product.")

    # Main content
    try:
        df = pd.read_csv('products.csv')
        if len(df) > 0:
            if st.button("🔄 Update Prices"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                scraper = AmazonScraper('products.csv', region=region)
                
                # Update prices with progress bar
                for index, row in df.iterrows():
                    status_text.text(f"Fetching price for {row['item_name']}...")
                    progress = (index + 1) / len(df)
                    progress_bar.progress(progress)
                    time.sleep(0.1)  # Small delay for visual feedback
                
                success = scraper.update_prices()
                if success:
                    st.success("✅ Prices updated successfully!")
                else:
                    st.error("❌ Error updating prices")
                
                # Clear progress
                progress_bar.empty()
                status_text.empty()
                
                # Reload the data
                df = pd.read_csv('products.csv')
            
            # Display current products and prices
            if os.path.exists("products.csv"):
                df = pd.read_csv("products.csv")
                if not df.empty:
                    st.header("📊 Product Prices")
                    
                    def make_clickable(url):
                        if pd.isna(url) or url in ["Not found", "Error", ""]:
                            return "Not available"
                        return f'<a href="{url}" target="_blank">View on Amazon</a>'

                    def format_price(row):
                        price = row['item_price']
                        if pd.isna(price) or price in ["Not found", "Error", ""]:
                            return "Not available"
                        if pd.isna(row['currency_symbol']) or pd.isna(row['currency']):
                            return str(price)
                        return f"{row['currency_symbol']}{price} ({row['currency']})"
                    
                    # Create a copy of the dataframe for display
                    display_df = df.copy()
                    
                    # Convert numeric columns to appropriate types
                    display_df['item_price'] = pd.to_numeric(display_df['item_price'], errors='coerce')
                    
                    # Format the display columns
                    display_df['Amazon Link'] = display_df['item_url'].apply(make_clickable)
                    display_df['Price'] = display_df.apply(format_price, axis=1)
                    
                    # Display the dataframe with clickable links
                    st.write(display_df[['item_name', 'Price', 'Amazon Link']].to_html(escape=False, index=False), unsafe_allow_html=True)
                    
                    if st.button("🔄 Refresh Prices"):
                        with st.spinner("Updating prices..."):
                            scraper = AmazonScraper("products.csv", region=region)
                            success = scraper.scrape_prices()
                            if success:
                                st.success("✅ Prices updated successfully!")
                                time.sleep(1)
                                st.experimental_rerun()
                            else:
                                st.error("❌ Error updating prices. Please try again.")
            
            # Option to remove products
            st.markdown("### ⚙️ Manage Products")
            product_to_remove = st.selectbox("Select product to remove", df['item_name'].tolist())
            if st.button("Remove Selected Product"):
                df = df[df['item_name'] != product_to_remove]
                df.to_csv('products.csv', index=False)
                st.success(f"Removed {product_to_remove} from tracking list!")
                st.rerun()
        
        else:
            st.info("👋 Welcome! Add some products to start tracking their prices.")
            
    except FileNotFoundError:
        st.warning("No products file found. Add some products to get started!")
        # Create empty products.csv
        pd.DataFrame(columns=['item_name', 'item_price', 'currency', 'currency_symbol', 'item_url']).to_csv('products.csv', index=False)
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()