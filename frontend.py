import io
import pandas as pd
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask import Flask, render_template, jsonify, Response, request
from datetime import datetime # Cần thiết cho tính Recency

# --- Khởi tạo ứng dụng ---
app = Flask(__name__, template_folder="templates", static_folder="static")

# --- Cấu hình ---
BACKEND_API_URL = "http://127.0.0.1:5000/api"

# --- Hàm hỗ trợ (Helpers) ---
def create_error_plot(message):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.text(0.5, 0.5, f"LỖI: {message}", ha='center', va='center', color='red')
    ax.set_title("Lỗi Biểu đồ")
    ax.axis('off')
    return Response(fig_to_png_bytes(fig), mimetype='image/png')

def fig_to_png_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()

def fetch_data():
    """
    Gọi API backend (port 5000) để lấy dữ liệu dashboard.
    """
    try:
        resp = requests.get(f"{BACKEND_API_URL}/all-data", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        df = pd.DataFrame(data)
        
        # Tiền xử lý kiểu dữ liệu sau khi tải
        if 'po_created_at' in df.columns:
            df['po_created_at'] = pd.to_datetime(df['po_created_at'], errors='coerce')
        if 'po_amount' in df.columns:
            df['po_amount'] = pd.to_numeric(df['po_amount'], errors='coerce').fillna(0)
            
        # Đảm bảo có cột ID_phap_nhan
        if 'ID' in df.columns and 'ID_phap_nhan' not in df.columns:
             df = df.rename(columns={'ID': 'ID_phap_nhan'})
            
        return df
    except requests.RequestException as e:
        print(f"Lỗi kết nối Backend hoặc API: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Lỗi xử lý dữ liệu: {e}")
        return pd.DataFrame()

def apply_filters_to_df(df):
    df_filtered = df.copy()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    loai_sp = request.args.get('loai_sp')
    ten_phap_nhan = request.args.get('ten_phap_nhan')
    if start_date:
        df_filtered = df_filtered[df_filtered['po_created_at'] >= start_date]
    if end_date:
        df_filtered = df_filtered[df_filtered['po_created_at'] <= end_date]
    if loai_sp:
        df_filtered = df_filtered[df_filtered['loai_sp'].astype(str).str.contains(loai_sp, case=False, na=False)]
    if ten_phap_nhan:
        df_filtered = df_filtered[df_filtered['ten_phap_nhan'].astype(str).str.contains(ten_phap_nhan, case=False, na=False)]
    return df_filtered

def calculate_rfm(df):
    df = df[df['po_amount'] > 0].copy()
    if 'ID_phap_nhan' not in df.columns:
        df = df.rename(columns={'ID': 'ID_phap_nhan'})
    df = df.dropna(subset=['ID_phap_nhan'])
    
    if df.empty:
        return pd.DataFrame()
    
    # Tính R, F, M
    NOW = pd.to_datetime(datetime.now().date())
    rfm_r = df.groupby('ID_phap_nhan')['po_created_at'].max().reset_index()
    rfm_r['Recency'] = (NOW - rfm_r['po_created_at']).dt.days
    rfm_r = rfm_r[['ID_phap_nhan', 'Recency']]
    rfm_f = df.groupby('ID_phap_nhan')['po_id'].nunique().reset_index().rename(columns={'po_id': 'Frequency'})
    rfm_m = df.groupby('ID_phap_nhan')['po_amount'].sum().reset_index().rename(columns={'po_amount': 'Monetary'})
    
    rfm_df = pd.merge(rfm_r, rfm_f, on='ID_phap_nhan', how='outer')
    rfm_df = pd.merge(rfm_df, rfm_m, on='ID_phap_nhan', how='outer')
    rfm_df['Frequency'] = rfm_df['Frequency'].fillna(0)
    rfm_df['Monetary'] = rfm_df['Monetary'].fillna(0)
    
    # Chia điểm R, F, M (Sử dụng qcut với fallback)
    def safe_qcut(series, labels, ascending=True):
        try:
            return pd.qcut(series, 5, labels=labels, duplicates='drop').astype('Int64')
        except:
            rank = series.rank(method='first', ascending=ascending)
            # Ánh xạ rank sang điểm 1-5
            return rank.apply(lambda x: min(5, max(1, int(x/len(series)*5)+1)))
            
    rfm_df['R_score'] = safe_qcut(rfm_df['Recency'], labels=[5, 4, 3, 2, 1], ascending=False)
    rfm_df['F_score'] = safe_qcut(rfm_df['Frequency'], labels=[1, 2, 3, 4, 5])
    rfm_df['M_score'] = safe_qcut(rfm_df['Monetary'], labels=[1, 2, 3, 4, 5])
    
    # Tạo Segment
    def rfm_segment(row):
        r, f, m = row['R_score'], row['F_score'], row['M_score']
        if r >= 4 and f >= 4 and m >= 4:
            return 'Champion'
        elif r >= 4 and f >= 3:
            return 'Loyal'
        elif r >= 3 and m >= 3:
            return 'Potential'
        elif r <= 2 and f <= 2:
            return 'At risk'
        else:
            return 'Others'
            
    rfm_df['Segment'] = rfm_df.apply(rfm_segment, axis=1)
    
    return rfm_df[['ID_phap_nhan', 'Recency', 'Frequency', 'Monetary', 'R_score', 'F_score', 'M_score', 'Segment']]
# --- Routes Trang (Views) ---

@app.route('/')
def index():
    return render_template('index.html')

# (Bạn có thể thêm các route khác như /po, /publisher, /manage nếu cần)
@app.route('/')
def home():
    return render_template("index.html")

@app.route('/publisher')
def publisher_page():
    return render_template("publisher.html")

@app.route('/manage')
def manage_page():
    return render_template("manage.html")

@app.route('/po')
def po_page():
    return render_template("po.html")

# --- Routes trả về Biểu đồ (Plots) ---

@app.route('/plot/monthly.png')
def plot_monthly():
    try:
        df = fetch_data() # Lấy tất cả
        df = apply_filters_to_df(df) # Lọc
        
        if df.empty or 'po_created_at' not in df.columns or 'po_id' not in df.columns:
            return create_error_plot("Không có dữ liệu (sau khi lọc).")
    except Exception as e:
        return create_error_plot(f"Lỗi tải dữ liệu:\n{e}")

    df['year_month'] = df['po_created_at'].dt.to_period('M').astype(str)
    
    monthly_agg = df.groupby('year_month').agg(
        po_amount_sum=('po_amount', 'sum'),
        po_id_count=('po_id', 'count')
    ).sort_index()

    if monthly_agg.empty:
        return create_error_plot("Không có dữ liệu (sau khi lọc).")

    fig, ax = plt.subplots(figsize=(18, 5)) 

    # 1. Vẽ Bar plot (Doanh thu)
    monthly_agg['po_amount_sum'].plot(
        kind='bar', 
        ax=ax, 
        color='C0',
        label='Tổng giá trị PO (Sum)'
    )
    ax.set_title('Doanh thu (Sum) và Số lượng (Count) PO theo tháng')
    ax.set_ylabel('Giá trị PO (Sum)')
    ax.set_xlabel('')

    # --- THÊM MỚI: Hiển thị số trên Bar (Doanh thu) ---
    # ax.patches chứa các hình chữ nhật (thanh bar)
    for p in ax.patches:
        # Lấy chiều cao (giá trị) của bar
        height = p.get_height()
        # Vị trí X (trung tâm bar)
        x_pos = p.get_x() + p.get_width() / 2.
        
        # Thêm text (annotate)
        ax.annotate(
            f'{height:,.0f}',    # Format số (ví dụ: 1,234,567)
            (x_pos, height),     # Vị trí (x, y) để ghim text
            ha='center',         # Căn giữa theo chiều ngang
            va='bottom',         # Căn đáy (để text bắt đầu từ điểm y)
            xytext=(0, 3),       # Offset (cách đỉnh bar 3 points)
            textcoords='offset points',
            fontsize=9
        )
    # --- KẾT THÚC THÊM MỚI (Bar) ---

    # 2. Tạo trục Y thứ hai (ax2)
    ax2 = ax.twinx()

    # 3. Vẽ Line plot (Số lượng)
    monthly_agg['po_id_count'].plot(
        kind='line', 
        ax=ax2, 
        color='C1',
        marker='o',
        label='Số lượng PO (Count)'
    )
    ax2.set_ylabel('Số lượng PO (Count)')

    # --- THÊM MỚI: Hiển thị số trên Line (Số lượng) ---
    # Lấy giá trị (count)
    counts = monthly_agg['po_id_count']
    
    for i, value in enumerate(counts):
        # x=i (0, 1, 2...), y=value
        ax2.annotate(
            f'{value:,.0f}',     # Format số (ví dụ: 1,234)
            (i, value),          # Vị trí (x, y) để ghim text
            ha='center',
            va='bottom',
            xytext=(0, 5),       # Offset (cách điểm 5 points)
            textcoords='offset points',
            fontsize=9,
            color='C1'           # Cùng màu với line
        )
    # --- KẾT THÚC THÊM MỚI (Line) ---
    
    # 4. Điều chỉnh ticks trục X
    ax.set_xticklabels(monthly_agg.index, rotation=0, ha='right')

    # 5. Gộp legend
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc='upper left')

    # (Lưu ý: Có thể cần điều chỉnh Y-limit để số không bị cắt)
    # Tăng 10% Y-limit trên để có không gian cho text
    ax.set_ylim(top=ax.get_ylim()[1] * 1.1)
    ax2.set_ylim(top=ax2.get_ylim()[1] * 1.1)

    plt.tight_layout()
    
    png = fig_to_png_bytes(fig)
    return Response(png, mimetype='image/png')

@app.route('/plot/campaign.png')
def plot_campaign():
    try:
        df = fetch_data() # Lấy tất cả
        df = apply_filters_to_df(df) # Lọc
    except Exception as e:
        return create_error_plot(f"Lỗi tải dữ liệu:\n{e}")

    if 'loai_sp' not in df.columns or df['loai_sp'].isna().all():
        return create_error_plot("Không có dữ liệu (sau khi lọc).")

    campaign = df.groupby('loai_sp')['po_amount'].sum().sort_values(ascending=False)
    
    if len(campaign) > 8:
        top = campaign.iloc[:8].copy()
        others_sum = campaign.iloc[8:].sum()
        if others_sum > 0:
            top['Khác'] = others_sum
        campaign = top
    
    if campaign.empty or campaign.sum() == 0:
         return create_error_plot("Không có dữ liệu (sau khi lọc).")

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(campaign.values, labels=campaign.index, autopct='%1.1f%%', startangle=140)
    ax.set_title('Tỷ trọng doanh thu theo loại sản phẩm')
    plt.tight_layout()
    
    png = fig_to_png_bytes(fig)
    return Response(png, mimetype='image/png')

@app.route('/plot/pareto.png')
def plot_pareto_segment():
    try:
        df_all = fetch_data() # Lấy tất cả
        df_filtered = apply_filters_to_df(df_all) # Lọc
        
        if df_filtered.empty:
            return create_error_plot("Không có dữ liệu (sau khi lọc).")
    except Exception as e:
        return create_error_plot(f"Lỗi tải dữ liệu:\n{e}")

    # Tính RFM trên dữ liệu đã lọc
    rfm = calculate_rfm(df_filtered)
    
    if rfm.empty:
        return create_error_plot("Không thể tính RFM (sau khi lọc).")

    seg_summary = rfm.groupby('Segment')['Monetary'].sum().sort_values(ascending=False).reset_index()
    if seg_summary.empty or seg_summary['Monetary'].sum() == 0:
        return create_error_plot("Không có doanh thu (sau khi lọc).")

    seg_summary['cum_percentage'] = seg_summary['Monetary'].cumsum() / seg_summary['Monetary'].sum() * 100

    fig, ax1 = plt.subplots(figsize=(10, 7))
    ax1.bar(seg_summary['Segment'], seg_summary['Monetary'], color='skyblue')
    ax1.set_xlabel('Phân khúc khách hàng (Segment)')
    ax1.set_ylabel('Doanh thu (Monetary)')
    ax1.tick_params(axis='x', rotation=0)

    ax2 = ax1.twinx()
    ax2.plot(seg_summary['Segment'], seg_summary['cum_percentage'], color='red', marker='o')
    ax2.set_ylabel('Tỷ lệ tích lũy (%)')
    ax2.set_ylim(0, 110)
    ax2.axhline(80, color='green', linestyle='--')
    ax2.text(len(seg_summary) - 1, 82, '80% Doanh thu', color='green', ha='right')

    plt.title('Pareto Doanh thu theo Phân khúc RFM')
    plt.tight_layout()

    png = fig_to_png_bytes(fig)
    return Response(png, mimetype='image/png')

def filter_by_top_revenue_contribution(df, threshold=0.8):
    if df.empty or 'ID_phap_nhan' not in df.columns or 'po_amount' not in df.columns:
        return pd.DataFrame()
    # 1. Tính tổng doanh thu theo ID_phap_nhan
    df_revenue = df.groupby('ID_phap_nhan')['po_amount'].sum().reset_index()
    df_revenue = df_revenue.rename(columns={'po_amount': 'Total_Revenue'})
    # 2. Sắp xếp giảm dần theo doanh thu
    df_revenue = df_revenue.sort_values(by='Total_Revenue', ascending=False)
    # 3. Tính tổng doanh thu toàn bộ
    total_all_revenue = df_revenue['Total_Revenue'].sum()
    if total_all_revenue == 0:
        return pd.DataFrame()
    # 4. Tính tỷ lệ đóng góp và tổng đóng góp tích lũy
    df_revenue['Contribution_Ratio'] = df_revenue['Total_Revenue'] / total_all_revenue
    df_revenue['Cumulative_Contribution'] = df_revenue['Contribution_Ratio'].cumsum()
    # 5. Xác định các pháp nhân cần giữ lại (cho đến khi vượt ngưỡng)
    top_publishers = []
    current_cumulative = 0
    for index, row in df_revenue.iterrows():
        top_publishers.append(row['ID_phap_nhan'])
        current_cumulative = row['Cumulative_Contribution']
        if current_cumulative >= threshold:
            break
    # 6. Lọc dữ liệu gốc
    df_filtered = df[df['ID_phap_nhan'].isin(top_publishers)]
    return df_filtered

@app.route('/api/rfm-data', methods=['GET'])
def api_rfm_data():
    try:
        df_all = fetch_data() # Lấy tất cả   
        df_filtered = apply_filters_to_df(df_all) # Lọc
        if df_filtered.empty or df_filtered['po_amount'].sum() == 0:
            return jsonify({
                "message": "Không có dữ liệu PO hợp lệ (sau khi lọc).", 
                "data": []
            }), 200
    except Exception as e:
        return jsonify({
            "message": f"Lỗi tải dữ liệu: {e}", 
            "data": []
        }), 500

    # THAY ĐỔI MỚI: Chỉ lấy dữ liệu của pháp nhân đóng góp >= 80% doanh thu
    # df_rfm_input = filter_by_top_revenue_contribution(df_filtered, 0.8) # Ngưỡng 80%
    df_rfm_input = df_filtered

    if df_rfm_input.empty:
        return jsonify({"message": "Không có dữ liệu pháp nhân Top 80% doanh thu.", "data": []}), 200
        
    # Tính RFM trên dữ liệu đã lọc (Top 80%)
    rfm_df = calculate_rfm(df_rfm_input)
    
    if rfm_df.empty:
        return jsonify({"message": "Không thể tính RFM (sau khi lọc Top 80%).", "data": []}), 200
        
    # Lấy metadata Tên Pháp nhân
    df_publisher_meta = df_all.dropna(subset=['ID_phap_nhan']).drop_duplicates(subset=['ID_phap_nhan'])[['ID_phap_nhan', 'ten_phap_nhan']]
    rfm_df = pd.merge(rfm_df, df_publisher_meta, on='ID_phap_nhan', how='left')
    
    # Chọn và sắp xếp lại cột
    # SỬA LỖI 2 (KeyError): Dùng tên cột chữ thường
    rfm_df = rfm_df[[
        'ID_phap_nhan', 'ten_phap_nhan', 
        'Segment', 'R_score', 'F_score', 'M_score', # <-- ĐÃ SỬA
        'Recency', 'Frequency', 'Monetary'
    ]].sort_values(by=['Monetary','R_score', 'F_score', 'M_score'], ascending=False)
    
    # Chuẩn hóa kiểu dữ liệu
    rfm_df['Recency'] = rfm_df['Recency'].astype('Int64').fillna('')
    rfm_df['Frequency'] = rfm_df['Frequency'].astype('Int64').fillna('')
    rfm_df['R_score'] = rfm_df['R_score'].astype('Int64').fillna('')
    rfm_df['F_score'] = rfm_df['F_score'].astype('Int64').fillna('')
    rfm_df['M_score'] = rfm_df['M_score'].astype('Int64').fillna('')

    rfm_data_list = rfm_df.fillna('').to_dict('records')

    return jsonify({"message": "Dữ liệu RFM đã sẵn sàng.", "data": rfm_data_list})

if __name__ == '__main__':
    # Chạy trên port 8000
    app.run(port=8000, debug=True)