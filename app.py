import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
from flask import Flask, render_template, request

app = Flask(__name__)

def calculate_max_pain(ticker_obj, expiry_date):
    try:
        chain = ticker_obj.option_chain(expiry_date)
        calls = chain.calls[['strike', 'openInterest']].fillna(0)
        puts = chain.puts[['strike', 'openInterest']].fillna(0)
        
        # Merge all unique strikes
        strikes = sorted(list(set(calls['strike']).union(set(puts['strike']))))
        
        results = []
        for s in strikes:
            # Pain = Intrinsic value if price expires at strike 's' * Open Interest
            c_pain = np.sum(np.maximum(0, s - calls['strike']) * calls['openInterest'])
            p_pain = np.sum(np.maximum(0, puts['strike'] - s) * puts['openInterest'])
            results.append({'strike': s, 'total_pain': c_pain + p_pain})

        df = pd.DataFrame(results)
        return df.loc[df['total_pain'].idxmin(), 'strike'] if not df.empty else None
    except Exception:
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    chart_html = None
    error = None
    symbol = ""

    if request.method == 'POST':
        symbol = request.form.get('symbol').strip().upper()
        tk = yf.Ticker(symbol)
        
        try:
            # Get current price
            current_price = tk.fast_info['lastPrice']
            expirations = tk.options
            
            if not expirations:
                error = f"No options data found for {symbol}."
            else:
                limit = min(15, len(expirations))
                summary_data = []
                
                for date in expirations[:limit]:
                    mp_strike = calculate_max_pain(tk, date)
                    if mp_strike:
                        summary_data.append({'Date': date, 'Max Pain': mp_strike})
                
                if summary_data:
                    df = pd.DataFrame(summary_data)
                    
                    # Create Plotly Figure
                    fig = go.Figure()
                    
                    # Max Pain Line
                    fig.add_trace(go.Scatter(
                        x=df['Date'], y=df['Max Pain'],
                        mode='lines+markers',
                        name='Max Pain Strike',
                        line=dict(color='#1f77b4', width=3)
                    ))
                    
                    # Current Price Line
                    fig.add_trace(go.Scatter(
                        x=df['Date'], y=[current_price] * len(df),
                        mode='lines',
                        name=f'Current Price (${current_price:.2f})',
                        line=dict(color='red', dash='dash')
                    ))

                    fig.update_layout(
                        title=f"Max Pain Forward Curve: {symbol}",
                        xaxis_title="Expiration Date",
                        yaxis_title="Price ($)",
                        template="plotly_white",
                        hovermode="x unified"
                    )
                    
                    chart_html = pio.to_html(fig, full_html=False)
                else:
                    error = "Could not calculate Max Pain for available dates."
        except Exception as e:
            error = f"Error retrieving data: {str(e)}"

    return render_template('index.html', chart_html=chart_html, error=error, symbol=symbol)

if __name__ == '__main__':
    app.run(debug=True)