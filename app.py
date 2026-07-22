import streamlit as st
import requests
from bs4 import BeautifulSoup
import csv
import re
import random
import time
from urllib.parse import urljoin
import json
import pandas as pd
from io import BytesIO, StringIO
import zipfile
import os
from PIL import Image, ImageEnhance, ImageOps

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="Image Edit + CSV Generator", page_icon="🖌️")

# ---------- INITIALIZE SESSION STATE (Data persist karne ke liye) ----------
if 'is_ready' not in st.session_state:
    st.session_state.is_ready = False
if 'csv_data' not in st.session_state:
    st.session_state.csv_data = None
if 'zip_data' not in st.session_state:
    st.session_state.zip_data = None
if 'df_preview' not in st.session_state:
    st.session_state.df_preview = None
if 'failed_urls' not in st.session_state:
    st.session_state.failed_urls = []
if 'total_rows' not in st.session_state:
    st.session_state.total_rows = 0

# ---------- ROTATING USER-AGENTS ----------
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/126.0'
]

# ---------- REWRITER ENGINE ----------
class SmartRewriter:
    def __init__(self):
        self.synonyms = {
            'great': 'exceptional', 'good': 'superior', 'best': 'top-tier',
            'durable': 'long-lasting', 'strong': 'robust', 'quality': 'premium',
            'design': 'aesthetic', 'feature': 'attribute', 'product': 'item',
            'amazing': 'remarkable', 'perfect': 'ideal', 'easy': 'effortless',
            'simple': 'straightforward', 'modern': 'contemporary', 'classic': 'timeless',
            'leather': 'premium hide', 'jacket': 'outerwear', 'biker': 'motorcycle'
        }
        self.intros = [
            "Discover the unrivaled ", "Experience next-level ",
            "Upgrade your lifestyle with ", "Engineered for excellence, "
        ]

    def rewrite(self, text):
        if not text or len(text) < 5: return text
        sentences = re.split(r'(?<=[.!?]) +', text)
        if len(sentences) > 2: random.shuffle(sentences)
        new_sentences = []
        for sent in sentences:
            words = sent.split()
            new_words = []
            for word in words:
                lower_word = word.lower().strip('.,!?')
                if lower_word in self.synonyms:
                    replacement = self.synonyms[lower_word]
                    if word[0].isupper(): replacement = replacement.capitalize()
                    if word.endswith('.'): replacement += '.'
                    new_words.append(replacement)
                else:
                    new_words.append(word)
            new_sentences.append(' '.join(new_words))
        rewritten = '. '.join(new_sentences)
        if len(rewritten) > 20:
            rewritten = random.choice(self.intros) + rewritten[0].lower() + rewritten[1:]
        return rewritten.strip()

# ---------- SAFE EXTRACTORS ----------
def safe_get_offer_price(offers):
    if isinstance(offers, dict): return offers.get('price', '')
    elif isinstance(offers, list) and len(offers) > 0:
        first = offers[0]
        if isinstance(first, dict): return first.get('price', '')
    return ''

def safe_get_sku(sku_data):
    if isinstance(sku_data, str): return sku_data
    elif isinstance(sku_data, list) and len(sku_data) > 0: return str(sku_data[0])
    return ''

def format_category(soup, default="Imported Products"):
    bread = soup.find('ul', {'class': re.compile(r'breadcrumb|breadcrumbs')})
    if bread:
        links = bread.find_all('a')
        if len(links) > 1:
            categories = [link.get_text(strip=True) for link in links[1:]]
            if categories: return ' > '.join(categories)
    return default

# ---------- IMAGE EDITOR ----------
def edit_image(img_data, filename):
    try:
        img = Image.open(BytesIO(img_data))
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        angle = random.uniform(-2.5, 2.5)
        img = img.rotate(angle, expand=False, fillcolor=(255, 255, 255))
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(random.uniform(0.92, 1.08))
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(random.uniform(0.95, 1.05))
        img = ImageOps.expand(img, border=3, fill='white')
        
        new_filename = f"edited_{int(time.time())}_{random.randint(1000,9999)}_{filename.split('/')[-1].split('?')[0]}"
        if not new_filename.lower().endswith(('.jpg', '.jpeg')):
            new_filename = new_filename.rsplit('.', 1)[0] + '.jpg'
        
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85, optimize=True)
        buffer.seek(0)
        return new_filename, buffer.getvalue()
    except Exception as e:
        try:
            new_filename = f"edited_{int(time.time())}_{random.randint(1000,9999)}_{filename.split('/')[-1].split('?')[0]}"
            if not new_filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                new_filename = new_filename.rsplit('.', 1)[0] + '.jpg'
            return new_filename, img_data
        except:
            return None, None

# ---------- SCRAPER ----------
def scrape_product(url, session, edit_images):
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    for attempt in range(2):
        try:
            resp = session.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            break
        except:
            if attempt == 0: time.sleep(5)
            else: return None, None, f"Failed"

    soup = BeautifulSoup(resp.text, 'lxml')
    base_url = f"{resp.url.split('/')[0]}//{resp.url.split('/')[2]}"
    product_data = {}
    
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            data_type = data.get('@type')
            is_product = False
            if isinstance(data_type, str) and data_type == 'Product': is_product = True
            elif isinstance(data_type, list) and 'Product' in data_type: is_product = True
            if is_product:
                product_data = data
                break
        except: pass

    title = product_data.get('name') or (soup.find('h1').get_text(strip=True) if soup.find('h1') else None)
    if not title:
        og_title = soup.find('meta', property='og:title')
        title = og_title.get('content') if og_title else url.split('/')[-1].replace('-', ' ')

    desc = product_data.get('description') or ''
    if not desc:
        desc_meta = soup.find('meta', attrs={'name': 'description'})
        desc = desc_meta.get('content') if desc_meta else ''
    if not desc or len(desc) < 20:
        og_desc = soup.find('meta', property='og:description')
        desc = og_desc.get('content') if og_desc else title

    price = safe_get_offer_price(product_data.get('offers'))
    if not price:
        price_span = soup.find('span', {'class': re.compile(r'price|amount|sale-price')})
        if price_span:
            match = re.search(r'[\d,]+\.?\d*', price_span.get_text())
            price = match.group() if match else '0'
        else: price = '0'

    sku_raw = safe_get_sku(product_data.get('sku'))
    if not sku_raw:
        sku_span = soup.find('span', {'class': re.compile(r'sku|id|model')})
        sku_raw = sku_span.get_text(strip=True) if sku_span else f"OLD-{random.randint(1000,9999)}"
    rand_suffix = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))
    new_parent_sku = f"CUSTOM-{rand_suffix}-{sku_raw}"

    # Images
    raw_image_urls = []
    if product_data.get('image'):
        if isinstance(product_data['image'], list): raw_image_urls.extend(product_data['image'])
        else: raw_image_urls.append(product_data['image'])
    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'): raw_image_urls.append(og_img.get('content'))
    for img in soup.find_all('img'):
        src = img.get('data-src') or img.get('src')
        if src and not src.endswith('.svg') and 'logo' not in src.lower():
            full_url = urljoin(base_url, src)
            if full_url not in raw_image_urls: raw_image_urls.append(full_url)
    raw_image_urls = [im for im in raw_image_urls if im.startswith('http')][:10]

    image_files = {}
    processed_image_urls = []
    image_zip_data = {}

    if edit_images:
        for img_url in raw_image_urls:
            try:
                img_resp = session.get(img_url, timeout=15)
                if img_resp.status_code == 200:
                    new_name, edited_data = edit_image(img_resp.content, img_url)
                    if new_name and edited_data:
                        image_files[img_url] = new_name
                        image_zip_data[new_name] = edited_data
                        processed_image_urls.append(new_name)
            except:
                processed_image_urls.append(img_url)
    else:
        processed_image_urls = raw_image_urls

    images_str = ', '.join(processed_image_urls) if processed_image_urls else ''

    category_str = format_category(soup, "Imported Products")
    if not category_str or category_str == "Imported Products":
        cat_from_ld = product_data.get('category', '')
        if cat_from_ld: category_str = cat_from_ld

    rewriter = SmartRewriter()
    new_title = rewriter.rewrite(title)

    offers = product_data.get('offers')
    variations_data = []
    if isinstance(offers, list) and len(offers) > 1:
        for offer in offers:
            if isinstance(offer, dict):
                var_sku = offer.get('sku', f'VAR-{len(variations_data)+1}')
                var_price = offer.get('price', price)
                var_attrs = {}
                if 'size' in offer: var_attrs['Size'] = offer['size']
                if 'color' in offer: var_attrs['Color'] = offer['color']
                if not var_attrs: var_attrs['Option'] = f'Variant {len(variations_data)+1}'
                variations_data.append({
                    'sku': var_sku, 'price': var_price, 'attrs': var_attrs,
                    'image': offer.get('image', '')
                })

    if variations_data:
        product_type = 'variable'
        parent_price = ''
    else:
        product_type = 'simple'
        parent_price = price

    attr_names = set(); attr_values_map = {}
    if variations_data:
        for var in variations_data:
            for key, val in var['attrs'].items():
                attr_names.add(key)
                if key not in attr_values_map: attr_values_map[key] = set()
                attr_values_map[key].add(val)
    attr_names = sorted(list(attr_names))
    attr_cols = {'Attribute 1 name': '', 'Attribute 1 value(s)': '', 'Attribute 2 name': '', 'Attribute 2 value(s)': ''}
    if attr_names:
        for i, name in enumerate(attr_names[:2]):
            vals = sorted(list(attr_values_map[name]))
            attr_cols[f'Attribute {i+1} name'] = name
            attr_cols[f'Attribute {i+1} value(s)'] = ' | '.join(vals)

    parent_row = {
        'Type': product_type, 'SKU': new_parent_sku, 'Name': new_title, 'Published': 1,
        'Regular price': parent_price, 'Categories': category_str, 'Images': images_str,
        'Attribute 1 name': attr_cols['Attribute 1 name'],
        'Attribute 1 value(s)': attr_cols['Attribute 1 value(s)'],
        'Attribute 2 name': attr_cols['Attribute 2 name'],
        'Attribute 2 value(s)': attr_cols['Attribute 2 value(s)'],
        'Parent': '', 'Stock': 10 if product_type == 'simple' else ''
    }
    results = [parent_row]

    if variations_data:
        for var in variations_data:
            var_sku = f"{new_parent_sku}-{var.get('sku', random.randint(100,999))}"
            var_price = var.get('price', price)
            var_attrs = var['attrs']
            attr1_val = list(var_attrs.values())[0] if len(var_attrs) > 0 else ''
            attr1_name = list(var_attrs.keys())[0] if len(var_attrs) > 0 else ''
            attr2_val = list(var_attrs.values())[1] if len(var_attrs) > 1 else ''
            attr2_name = list(var_attrs.keys())[1] if len(var_attrs) > 1 else ''

            var_img = var.get('image', '')
            var_images_str = ''
            if edit_images and var_img:
                try:
                    img_resp = session.get(var_img, timeout=15)
                    if img_resp.status_code == 200:
                        new_name, edited_data = edit_image(img_resp.content, var_img)
                        if new_name and edited_data:
                            image_zip_data[new_name] = edited_data
                            var_images_str = new_name
                except:
                    var_images_str = var_img
            if not var_images_str:
                var_images_str = images_str

            variation_row = {
                'Type': 'variation', 'SKU': var_sku,
                'Name': f"{new_title} - {attr1_val} {attr2_val}".strip() if (attr1_val or attr2_val) else f"{new_title} - Var",
                'Published': 1, 'Regular price': var_price, 'Categories': category_str,
                'Images': var_images_str, 'Attribute 1 name': attr1_name,
                'Attribute 1 value(s)': attr1_val, 'Attribute 2 name': attr2_name,
                'Attribute 2 value(s)': attr2_val, 'Parent': new_parent_sku, 'Stock': 10
            }
            results.append(variation_row)

    return results, image_zip_data, None

# ---------- UI STARTS HERE ----------
st.title("🖌️ Duplicate-Proof CSV + Image ZIP Generator")
st.markdown("**Scrape | Rewrite | Edit Images | WooCommerce Ready (13 Columns)**")

with st.expander("📌 Important - Buttons ab gayab nahi honge!", expanded=True):
    st.write("""
    - **CSV aur ZIP dono ek saath dikhenge**, chahe pehle koi bhi download karo.
    - **Session State** use ho rahi hai, isliye data memory mein rehta hai.
    - Naya batch run karne ke liye **'🔄 Reset & New Batch'** button dabao.
    """)

urls_input = st.text_area("🔗 Paste Product URLs (Max 20-30 per batch):", height=120)

col1, col2 = st.columns(2)
with col1:
    edit_images = st.checkbox("🖌️ Edit Images (Avoid Duplicates)", value=True)
with col2:
    base_url = st.text_input("🌐 Base URL for Images (Optional):", 
                             placeholder="https://domain.com/wp-content/uploads/")

EXACT_COLUMNS = [
    'Type', 'SKU', 'Name', 'Published', 'Regular price', 'Categories', 'Images',
    'Attribute 1 name', 'Attribute 1 value(s)', 'Attribute 2 name', 'Attribute 2 value(s)',
    'Parent', 'Stock'
]

# ---------- GENERATE BUTTON ----------
if st.button("🚀 Generate CSV + ZIP", type="primary"):
    if not urls_input.strip():
        st.error("❌ Kuch URLs toh daalo!")
    else:
        urls = [u.strip() for u in re.split(r'[,\s]+', urls_input) if u.strip().startswith('http')]
        if not urls:
            st.error("❌ Valid URL nahi mili.")
        else:
            # Reset previous session data before new run
            st.session_state.is_ready = False
            st.session_state.csv_data = None
            st.session_state.zip_data = None
            st.session_state.df_preview = None
            st.session_state.failed_urls = []
            st.session_state.total_rows = 0

            progress_bar = st.progress(0)
            status_text = st.empty()
            all_rows = []
            failed_urls = []
            all_image_data = {}
            
            session = requests.Session()
            total_urls = len(urls)
            
            for idx, url in enumerate(urls):
                status_text.text(f"⏳ Processing {idx+1}/{total_urls}...")
                results, image_data, error = scrape_product(url, session, edit_images)
                if results:
                    all_rows.extend(results)
                    if image_data:
                        all_image_data.update(image_data)
                else:
                    failed_urls.append(url)
                progress_bar.progress((idx + 1) / total_urls)
                time.sleep(random.uniform(4.0, 6.5))
            
            progress_bar.progress(1.0)
            status_text.text("✅ Processing Complete!")
            
            if not all_rows:
                st.error("❌ Koi product scrape nahi ho saka.")
                st.stop()
            
            # Apply Base URL to Images in CSV
            for row in all_rows:
                img_col = row.get('Images', '')
                if img_col and base_url:
                    imgs = img_col.split(', ')
                    new_imgs = []
                    for img in imgs:
                        if not img.startswith('http'):
                            new_imgs.append(f"{base_url.rstrip('/')}/{img.lstrip('/')}")
                        else:
                            new_imgs.append(img)
                    row['Images'] = ', '.join(new_imgs)
                elif img_col and not base_url:
                    pass

            df = pd.DataFrame(all_rows, columns=EXACT_COLUMNS)
            for col in EXACT_COLUMNS:
                if col not in df.columns: df[col] = ''
            df = df[EXACT_COLUMNS]
            
            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            csv_data = csv_buffer.getvalue()
            
            zip_buffer = BytesIO()
            has_zip = False
            if all_image_data:
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for filename, binary_data in all_image_data.items():
                        zip_file.writestr(filename, binary_data)
                zip_buffer.seek(0)
                zip_ready = zip_buffer.getvalue()
                has_zip = True
            else:
                zip_ready = None

            # --- SAVE TO SESSION STATE ---
            st.session_state.csv_data = csv_data
            st.session_state.zip_data = zip_ready
            st.session_state.df_preview = df
            st.session_state.failed_urls = failed_urls
            st.session_state.total_rows = len(all_rows)
            st.session_state.is_ready = True
            st.session_state.has_zip = has_zip
            
            st.rerun()  # Force rerun to show persistent buttons

# ---------- DISPLAY PERSISTENT DOWNLOAD BUTTONS (Ye kabhi gayab nahi honge) ----------
if st.session_state.is_ready:
    st.success(f"🎯 {st.session_state.total_rows} rows generated! {len(st.session_state.failed_urls)} failed.")
    if st.session_state.failed_urls:
        with st.expander(f"⚠️ Show {len(st.session_state.failed_urls)} Failed URLs"):
            st.write('\n'.join(st.session_state.failed_urls))
    
    st.subheader("📊 Preview (First 5 rows)")
    st.dataframe(st.session_state.df_preview.head(5))
    
    col_a, col_b, col_c = st.columns([2, 2, 1])
    with col_a:
        st.download_button(
            label="⬇️ Download CSV (WooCommerce Ready)",
            data=st.session_state.csv_data,
            file_name=f"leather_store_{int(time.time())}.csv",
            mime="text/csv",
            use_container_width=True,
            key="csv_download"  # Unique key to avoid conflicts
        )
    
    with col_b:
        if st.session_state.has_zip and st.session_state.zip_data:
            st.download_button(
                label=f"⬇️ Download Images ZIP ({len(st.session_state.zip_data) // 1024} KB approx)",
                data=st.session_state.zip_data,
                file_name=f"edited_images_{int(time.time())}.zip",
                mime="application/zip",
                use_container_width=True,
                key="zip_download"
            )
        else:
            st.info("No edited images generated for ZIP.")
    
    with col_c:
        # Reset button to clear state and start fresh
        if st.button("🔄 Reset & New Batch", use_container_width=True):
            st.session_state.is_ready = False
            st.session_state.csv_data = None
            st.session_state.zip_data = None
            st.session_state.df_preview = None
            st.session_state.failed_urls = []
            st.session_state.total_rows = 0
            st.session_state.has_zip = False
            st.rerun()

st.caption("🖌️ Persistent Download Buttons | Session State Active | CSV + ZIP dono saath rahenge!")
