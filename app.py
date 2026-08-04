import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import random
import time
import json
from urllib.parse import urljoin, urlparse
import pandas as pd
from io import BytesIO, StringIO
import zipfile
from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFilter

# ============================================================
# SESSION STATE INIT
# ============================================================
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
if 'has_zip' not in st.session_state:
    st.session_state.has_zip = False

# Batch Processing State
if 'batch_index' not in st.session_state:
    st.session_state.batch_index = 0
if 'all_final_rows' not in st.session_state:
    st.session_state.all_final_rows = []
if 'all_image_data' not in st.session_state:
    st.session_state.all_image_data = {}
if 'all_failed' not in st.session_state:
    st.session_state.all_failed = []
if 'total_urls' not in st.session_state:
    st.session_state.total_urls = 0
if 'is_processing' not in st.session_state:
    st.session_state.is_processing = False
if 'all_urls' not in st.session_state:
    st.session_state.all_urls = []

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(page_title="Universal E-commerce Extractor V5.1", page_icon="🛒")
st.title("🛒 UNIVERSAL E-COMMERCE EXTRACTOR V5.1 (AI DESCRIPTIONS)")
st.markdown("**Gemini AI for Unique Descriptions | Smart Titles | Variations Fixed**")

st.components.v1.html("""
<script>
    setInterval(function() {
        console.log("🛡️ Keep-Alive Ping");
    }, 2000);
</script>
""", height=0)

# ============================================================
# BRANDING STUDIO UI
# ============================================================
st.subheader("🎨 Branding Studio (Optional)")
with st.expander("⚙️ Configure Image Branding", expanded=True):
    col_a, col_b = st.columns(2)
    with col_a:
        st.checkbox("🖼️ Add Corner Logo (Top-Left)", key="enable_logo", value=False)
        if st.session_state.get("enable_logo", False):
            st.file_uploader("Upload Corner Logo", type=['png', 'jpg', 'jpeg'], key="logo_uploader")
        
        st.checkbox("🔤 Add Center Watermark", key="enable_watermark", value=False)
        if st.session_state.get("enable_watermark", False):
            st.radio("Watermark Type", ["Text", "Image Logo"], key="watermark_type", horizontal=True)
            st.slider("Watermark Size (%)", 5, 50, 15, key="watermark_size")
            st.slider("Watermark Opacity (%)", 10, 80, 20, key="watermark_opacity")
            if st.session_state.get("watermark_type") == "Text":
                st.text_input("Watermark Text", "YourBrand.com", key="watermark_text")
            else:
                st.file_uploader("Upload Watermark Logo (PNG)", type=['png', 'jpg', 'jpeg'], key="watermark_logo_uploader")
        
        st.checkbox("🌑 Drop Shadow", key="enable_shadow", value=False)
        st.checkbox("🔄 Rounded Corners", key="enable_rounded", value=False)
        st.checkbox("🔄 Mirror Flip (Anti-Duplicate)", key="enable_flip", value=True)

    with col_b:
        st.checkbox("🖼️ Add Border", key="enable_border", value=False)
        if st.session_state.get("enable_border", False):
            st.color_picker("Border Color", "#000000", key="border_color")
        
        st.checkbox("🌈 Add Gradient Frame", key="enable_gradient", value=False)
        if st.session_state.get("enable_gradient", False):
            st.color_picker("Gradient Color 1", "#FF5733", key="grad_color_1")
            st.color_picker("Gradient Color 2", "#33FF57", key="grad_color_2")
        
        st.checkbox("✨ Brightness/Contrast Tweak", key="enable_enhance", value=True)

# ============================================================
# CONTENT SETTINGS (WITH GEMINI AI TOGGLE)
# ============================================================
st.subheader("📝 Content Settings")
with st.expander("⚙️ Configure Product Content", expanded=True):
    col_ct1, col_ct2 = st.columns(2)
    with col_ct1:
        st.text_area("🏪 Store / Niche Context (optional)", key="ai_store_context",
                      placeholder="e.g. Premium leather jackets store, target audience: men & women 20-45",
                      height=80)
        
        st.checkbox("✨ Auto-Generate Unique Product Title (from specs + material + color)", 
                    key="smart_title_enabled", value=True)
    
    with col_ct2:
        st.slider("🖼️ Max Gallery Images per Product", 3, 20, 10, key="max_gallery_images")
    
    # ============================================================
    # 🔥 NEW: GEMINI AI TOGGLE + API KEY
    # ============================================================
    st.markdown("---")
    st.checkbox("🚀 AI-Powered Descriptions (Google Gemini — Free Tier)", key="ai_enabled", value=False,
                help="Enabled: Uses Gemini to write unique, SEO-optimized descriptions. Disabled: Uses local rewriter.")
    
    if st.session_state.get("ai_enabled", False):
        col_key1, col_key2 = st.columns([2, 1])
        with col_key1:
            st.text_input("🔑 Gemini API Key", type="password", key="gemini_api_key",
                          help="Get your free key from https://aistudio.google.com/apikey")
        with col_key2:
            st.selectbox("Model", ["gemini-1.5-flash", "gemini-1.5-pro"], key="gemini_model",
                         help="Flash = faster, Pro = better quality (slightly slower)")
        st.caption("⚠️ Free tier has rate limits (60 requests/min). Tool will auto-fallback to local rewriter if AI fails.")
    else:
        # Clear API key from session if toggle is off
        if 'gemini_api_key' in st.session_state:
            st.session_state.gemini_api_key = ""

# ============================================================
# MAIN INPUTS
# ============================================================
st.subheader("📥 Input & Controls")
edit_images = st.checkbox("🖌️ Enable Image Editing (Master Switch)", value=True)

export_format = st.radio(
    "📦 Export CSV Format",
    ["🛍️ Shopify CSV", "🛒 WooCommerce CSV"],
    key="export_format",
    horizontal=True
)

col_inp1, col_inp2 = st.columns([3, 1])
with col_inp1:
    urls_input = st.text_area("🔗 Paste Product URLs (One per line):", height=150)
with col_inp2:
    base_url = st.text_input("🌐 Base URL:", placeholder="https://domain.com/wp-content/uploads/")

BATCH_SIZE = 30

# ============================================================
# HELPER: GET BRANDING CONFIG
# ============================================================
def get_branding_config():
    corner_logo_bytes = None
    if st.session_state.get("enable_logo", False):
        uploaded = st.session_state.get("logo_uploader", None)
        if uploaded is not None:
            corner_logo_bytes = uploaded.getvalue()
    
    watermark_logo_bytes = None
    if st.session_state.get("enable_watermark", False) and st.session_state.get("watermark_type") == "Image Logo":
        uploaded = st.session_state.get("watermark_logo_uploader", None)
        if uploaded is not None:
            watermark_logo_bytes = uploaded.getvalue()
    
    return {
        'edit_images': edit_images,
        'enable_flip': st.session_state.get("enable_flip", True),
        'enable_enhance': st.session_state.get("enable_enhance", True),
        'enable_logo': st.session_state.get("enable_logo", False),
        'corner_logo_bytes': corner_logo_bytes,
        'enable_watermark': st.session_state.get("enable_watermark", False),
        'watermark_type': st.session_state.get("watermark_type", "Text"),
        'watermark_text': st.session_state.get("watermark_text", "YourBrand.com"),
        'watermark_logo_bytes': watermark_logo_bytes,
        'watermark_size': st.session_state.get("watermark_size", 15),
        'watermark_opacity': st.session_state.get("watermark_opacity", 20),
        'enable_border': st.session_state.get("enable_border", False),
        'border_color': st.session_state.get("border_color", "#000000"),
        'enable_gradient': st.session_state.get("enable_gradient", False),
        'grad_color_1': st.session_state.get("grad_color_1", "#FF5733"),
        'grad_color_2': st.session_state.get("grad_color_2", "#33FF57"),
        'enable_shadow': st.session_state.get("enable_shadow", False),
        'enable_rounded': st.session_state.get("enable_rounded", False),
        'max_gallery_images': st.session_state.get("max_gallery_images", 10),
        'store_context': st.session_state.get("ai_store_context", ""),
        'export_format': 'woocommerce' if st.session_state.get("export_format", "🛍️ Shopify CSV").startswith("🛒") else 'shopify',
        'smart_title_enabled': st.session_state.get("smart_title_enabled", True),
        # AI Settings
        'ai_enabled': st.session_state.get("ai_enabled", False),
        'gemini_api_key': st.session_state.get("gemini_api_key", "").strip(),
        'gemini_model': st.session_state.get("gemini_model", "gemini-1.5-flash"),
    }

# ============================================================
# SMART REWRITER (LOCAL FALLBACK + BULLET SPECS)
# ============================================================
class SmartRewriter:
    def __init__(self):
        self.hook_pool = [
            ("Meet the {title} — ", "a piece that redefines what {category} should feel like."),
            ("Say hello to the {title}, ", "where quality meets everyday functionality."),
            ("Introducing the {title}, ", "designed for those who value both style and substance."),
            ("The {title} is here — ", "crafted to become your go-to {category} for years to come."),
            ("Step into the {title} — ", "a fresh take on classic {category} design."),
            ("Discover the {title}, ", "where premium materials meet thoughtful craftsmanship."),
            ("Elevate your wardrobe with the {title}, ", "a {category} that stands out for all the right reasons."),
            ("Experience the {title} — ", "built with the kind of care that shows in every detail."),
            ("The {title} isn't just another {category}; ", "it's the one you'll reach for time and again."),
            ("Get to know the {title}, ", "crafted to look good, feel great, and last through every season."),
        ]
        self.benefit_pool = [
            "designed with your comfort in mind from the very first wear",
            "built to handle everyday life without losing its shape or charm",
            "crafted with an eye for both style and lasting quality",
            "made to feel just as good as it looks",
            "put together with genuine care for fit, feel, and finish",
            "a favorite for anyone who wants quality without the fuss",
            "built to last and engineered to perform",
            "designed for real life — not just the showroom",
        ]
        self.feature_pool = [
            "Premium materials chosen for comfort and long-lasting wear",
            "Thoughtful construction that holds its shape use after use",
            "A comfortable, true-to-size fit made for all-day wear",
            "Versatile enough to dress up or down for any occasion",
            "Carefully finished details for a polished, put-together look",
            "Easy to care for so it stays looking great with minimal effort",
            "A timeless design that won't feel out of place next season",
            "Reinforced stitching and finishing where it matters most",
            "Breathable, comfortable feel that fits real, everyday life",
            "Color and finish that stay true wash after wash",
            "Precision engineering for lasting durability",
            "Premium hardware and closures for reliable everyday use",
        ]
        self.cta_pool = [
            "If you've been searching for something reliable and good-looking, this is worth adding to your cart.",
            "We think you'll love how it feels the moment you try it — go ahead and make it yours.",
            "A simple, no-guesswork way to upgrade your everyday look.",
            "Treat yourself to something that's built to last and easy to love.",
            "Add it to your collection today — we're confident it'll become a regular favorite.",
            "Still deciding? Our team is always happy to help you pick the right fit before you order.",
            "Take it home and see the difference quality makes.",
            "Experience the difference for yourself — order now and feel the quality.",
        ]
        self.seo_hooks = [
            "Shop the {title} today.",
            "Order your {title} now.",
            "Discover the {title} collection.",
            "The {title} is available now.",
            "Elevate your style with the {title}.",
            "Experience quality with the {title}.",
            "Get the {title} at the best price.",
            "Find your perfect {title} here.",
        ]
        self.used_hooks = []
        self.used_ctas = []
        self.used_seo = []
        self.used_features = []

    def _get_unique(self, pool, used_list, max_attempts=20):
        if len(used_list) >= len(pool) * 0.7:
            used_list.clear()
        for _ in range(max_attempts):
            item = random.choice(pool)
            if item not in used_list:
                used_list.append(item)
                return item
        item = random.choice(pool)
        used_list.append(item)
        return item

    def _clean_text(self, text):
        text = re.sub(r'<[^<]+?>', ' ', text or '')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _synonym_pass(self, text):
        synonyms = {
            'great': 'exceptional', 'good': 'superior', 'best': 'top-tier',
            'durable': 'long-lasting', 'strong': 'robust', 'quality': 'premium',
            'amazing': 'remarkable', 'perfect': 'ideal', 'easy': 'effortless',
            'simple': 'straightforward', 'modern': 'contemporary', 'classic': 'timeless',
            'beautiful': 'exquisite', 'nice': 'fantastic', 'cool': 'stylish',
            'high-quality': 'superior-grade', 'comfortable': 'ultra-comfortable',
            'soft': 'plush', 'lightweight': 'featherlight', 'stylish': 'fashion-forward',
        }
        protected = {
            'leather', 'jacket', 'biker', 'motorcycle', 'hide', 'zip', 'pocket',
            'collar', 'sleeve', 'fit', 'style', 'men', 'women', 'unisex', 'black',
            'brown', 'tan', 'maroon', 'red', 'blue', 'green', 'grey', 'white'
        }
        sentences = re.split(r'(?<=[.!?]) +', text)
        new_sentences = []
        for sent in sentences:
            words = sent.split()
            new_words = []
            for word in words:
                lower_word = word.lower().strip('.,!?')
                if lower_word in synonyms and lower_word not in protected:
                    replacement = synonyms[lower_word]
                    if word[:1].isupper():
                        replacement = replacement.capitalize()
                    if word.endswith('.'):
                        replacement += '.'
                    new_words.append(replacement)
                else:
                    new_words.append(word)
            new_sentences.append(' '.join(new_words))
        return ' '.join(new_sentences).strip()

    def _format_specs_as_bullets(self, specs_text, title):
        if not specs_text or len(specs_text.strip()) < 10:
            return []
        if '<li>' in specs_text or '•' in specs_text or re.search(r'\n\s*[-•]', specs_text):
            cleaned = re.sub(r'<[^<]+?>', ' ', specs_text)
            items = re.split(r'\n\s*[-•]\s*', cleaned)
            items = [i.strip() for i in items if i.strip()]
            if items:
                return items
        separators = r'\n|;|,\.\s*|•|\*'
        items = re.split(separators, specs_text)
        items = [i.strip() for i in items if i.strip() and len(i.strip()) > 5]
        if len(items) < 3:
            kv_pattern = re.compile(r'([A-Za-z\s]+):\s*([^,;\n]+)')
            matches = kv_pattern.findall(specs_text)
            if matches:
                items = [f"{k.strip()}: {v.strip()}" for k, v in matches]
        return items[:8]

    def generate_seo_content(self, title, raw_desc, category=None, store_context=None, specs_text=None):
        # Local fallback logic (same as V5.0)
        hook_template, hook_benefit = self._get_unique(self.hook_pool, self.used_hooks)
        hook = hook_template.format(title=title)
        benefit = hook_benefit.format(category=category or 'piece')
        niche_line = f" Perfect for shoppers who care about {store_context.strip().rstrip('.')}." if store_context else ""
        intro = f"{hook}{benefit}.{niche_line}"
        
        spec_items = self._format_specs_as_bullets(specs_text or raw_desc, title)
        num_features = random.randint(3, 5)
        features = []
        for _ in range(num_features):
            features.append(self._get_unique(self.feature_pool, self.used_features))
        if category:
            features.append(f"Thoughtfully categorized under {category.split('>')[-1].strip()}")
        
        all_bullets = spec_items[:4] + features
        feature_html = ''.join(f"<li>{item}</li>" for item in all_bullets[:8])
        cta = self._get_unique(self.cta_pool, self.used_ctas)
        
        parts = [f"<p>{intro}</p>"]
        if spec_items:
            parts.append(f"<ul>{feature_html}</ul>")
        parts.append(f"<p>{cta}</p>")
        description_html = ''.join(parts)
        
        seo_hook = self._get_unique(self.seo_hooks, self.used_seo)
        seo_title = f"{title} — {seo_hook.format(title=title)}"
        if len(seo_title) > 60:
            seo_title = seo_title[:57] + '...'
        
        plain_intro = re.sub(r'<[^<]+?>', ' ', intro)[:120]
        seo_description = f"{plain_intro} Discover the {title} collection today."
        if len(seo_description) > 160:
            seo_description = seo_description[:157] + '...'
        
        short_desc = plain_intro[:100]
        if len(short_desc) > 100:
            short_desc = short_desc[:97] + '...'
        
        return {
            'description_html': description_html,
            'seo_title': seo_title,
            'seo_description': seo_description,
            'short_description': short_desc,
            'specs_bullets': all_bullets
        }

# ============================================================
# 🔥 GEMINI AI DESCRIPTION GENERATOR
# ============================================================
def generate_ai_description_gemini(title, specs, category, store_context, api_key, model_name):
    """Call Gemini API to generate unique, SEO-optimized description with bullet points."""
    if not api_key or not title:
        return None
    
    # Build prompt
    prompt = f"""You are an expert e-commerce copywriter for a store: {store_context if store_context else 'Premium Products'}.
Write a unique, compelling, and SEO-optimized description for the product: "{title}".
Category: {category}
Details/Specifications: {specs}

Your response MUST be in EXACTLY this format with these headers on separate lines:

### SEO TITLE
[Write a catchy SEO title max 60 characters]

### SHORT DESCRIPTION
[Write a short description max 200 characters]

### LONG DESCRIPTION
[Write a long, sales-focused description. Use <ul><li> bullet points for features/specs. Use <p> for paragraphs. Make it professional and unique.]

### META DESCRIPTION
[Write a meta description max 160 characters]

Make sure the content is original, flows naturally, and persuades the customer to buy.
"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 1024,
            "topP": 0.95
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            try:
                text = data['candidates'][0]['content']['parts'][0]['text']
                return parse_ai_response(text, title)
            except (KeyError, IndexError):
                return None
        else:
            # Rate limit or error
            return None
    except Exception:
        return None

def parse_ai_response(text, fallback_title):
    """Parse the structured AI response into a dictionary."""
    result = {
        'seo_title': f"{fallback_title} — Premium Quality",
        'short_description': '',
        'description_html': '',
        'seo_description': ''
    }
    
    # Simple parsing using headers
    sections = {
        '### SEO TITLE': 'seo_title',
        '### SHORT DESCRIPTION': 'short_description',
        '### LONG DESCRIPTION': 'description_html',
        '### META DESCRIPTION': 'seo_description'
    }
    
    current_section = None
    current_content = []
    
    for line in text.split('\n'):
        line = line.strip()
        if line in sections:
            # Save previous section
            if current_section and current_content:
                clean_content = ' '.join(current_content).strip()
                result[sections[current_section]] = clean_content
            current_section = line
            current_content = []
        elif current_section:
            current_content.append(line)
    
    # Save last section
    if current_section and current_content:
        clean_content = ' '.join(current_content).strip()
        if current_section in sections:
            result[sections[current_section]] = clean_content
    
    # Fallback: Ensure long description has HTML paragraphs if missing
    if result['description_html'] and not '<p>' in result['description_html'] and not '<ul>' in result['description_html']:
        # Try to split into paragraphs
        paragraphs = result['description_html'].split('\n\n')
        html_parts = []
        for p in paragraphs:
            p = p.strip()
            if p:
                # Check if it contains bullet-like patterns
                if '•' in p or '-' in p:
                    items = [i.strip() for i in re.split(r'[•\-]\s*', p) if i.strip()]
                    if items:
                        html_parts.append('<ul><li>' + '</li><li>'.join(items) + '</li></ul>')
                    else:
                        html_parts.append(f"<p>{p}</p>")
                else:
                    html_parts.append(f"<p>{p}</p>")
        result['description_html'] = ''.join(html_parts)
    
    # Truncate lengths
    if len(result['seo_title']) > 70:
        result['seo_title'] = result['seo_title'][:67] + '...'
    if len(result['seo_description']) > 165:
        result['seo_description'] = result['seo_description'][:162] + '...'
    if len(result['short_description']) > 250:
        result['short_description'] = result['short_description'][:247] + '...'
    
    return result

# ============================================================
# EXTRACTORS
# ============================================================
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

def safe_get_brand(brand_data):
    if isinstance(brand_data, str): return brand_data
    if isinstance(brand_data, dict): return brand_data.get('name', '')
    if isinstance(brand_data, list) and brand_data:
        return safe_get_brand(brand_data[0])
    return ''

def format_category(soup, product_data=None, title=None, default="Uncategorized"):
    product_data = product_data or {}
    title_norm = re.sub(r'[^a-z0-9]', '', (title or '').lower())

    def _is_product_title(name):
        if not title_norm or not name:
            return False
        name_norm = re.sub(r'[^a-z0-9]', '', str(name).lower())
        if not name_norm:
            return False
        return name_norm == title_norm or (len(name_norm) > 6 and name_norm in title_norm)

    def _is_home(name):
        if not name:
            return False
        return str(name).strip().lower() in ('home', 'homepage', 'home page', 'main', 'shop', 'store')

    cat_field = product_data.get('category')
    if isinstance(cat_field, str) and cat_field.strip() and not _is_product_title(cat_field):
        return cat_field.strip()
    if isinstance(cat_field, list):
        cat_names = [c.strip() for c in cat_field if isinstance(c, str) and c.strip() and not _is_product_title(c)]
        if cat_names:
            return ' > '.join(cat_names)

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            candidates = data if isinstance(data, list) else [data]
            for entry in candidates:
                if isinstance(entry, dict) and entry.get('@type') == 'BreadcrumbList':
                    items = sorted(entry.get('itemListElement', []), key=lambda x: x.get('position', 0))
                    names = [it.get('name') or (it.get('item', {}).get('name') if isinstance(it.get('item'), dict) else None)
                             for it in items]
                    names = [n for n in names if n]
                    if names and _is_product_title(names[-1]):
                        names = names[:-1]
                    names = [n for n in names if not _is_home(n)]
                    if names:
                        return ' > '.join(names)
        except Exception:
            pass

    bread = (soup.find(['ul', 'nav', 'ol'], {'class': re.compile(r'breadcrumb', re.I)})
             or soup.find(attrs={'aria-label': re.compile(r'breadcrumb', re.I)}))
    if bread:
        links = bread.find_all('a')
        if links:
            categories = [link.get_text(strip=True) for link in links]
            if categories and _is_product_title(categories[-1]):
                categories = categories[:-1]
            categories = [c for c in categories if not _is_home(c)]
            if categories:
                return ' > '.join(categories)
    return default

def generate_handle(title):
    handle = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    if len(handle) > 200:
        handle = handle[:200].rsplit('-', 1)[0]
    return handle

def extract_title(soup, product_data, url):
    title = product_data.get('name')
    if not title:
        itemprop = soup.find(attrs={'itemprop': 'name'})
        if itemprop:
            title = itemprop.get_text(strip=True)
    if not title and soup.find('h1'):
        title = soup.find('h1').get_text(strip=True)
    if not title:
        og_title = soup.find('meta', property='og:title')
        title = og_title.get('content') if og_title else None
    if not title and soup.find('title'):
        title = soup.find('title').get_text(strip=True)
    if not title:
        title = url.split('/')[-1].replace('-', ' ').replace('_', ' ')
    return title.strip()

def extract_raw_description(soup, product_data):
    raw_desc = product_data.get('description') or ''
    if not raw_desc:
        itemprop = soup.find(attrs={'itemprop': 'description'})
        if itemprop:
            raw_desc = itemprop.get_text(strip=True)
    if not raw_desc:
        woo = soup.find('div', {'class': re.compile(r'woocommerce-product-details__short-description')})
        if woo:
            raw_desc = woo.get_text(' ', strip=True)
    if not raw_desc:
        magento = soup.find('div', {'class': re.compile(r'product.*description|description.*value', re.I)})
        if magento:
            raw_desc = magento.get_text(' ', strip=True)
    if not raw_desc:
        desc_meta = soup.find('meta', attrs={'name': 'description'})
        raw_desc = desc_meta.get('content') if desc_meta else ''
    if not raw_desc or len(raw_desc) < 20:
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            raw_desc = og_desc.get('content')
    return raw_desc

def extract_site_meta_title(soup, fallback_title):
    meta = soup.find('meta', attrs={'name': 'title'})
    if meta and meta.get('content'):
        return meta.get('content').strip()
    og = soup.find('meta', property='og:title')
    if og and og.get('content'):
        return og.get('content').strip()
    if soup.find('title'):
        t = soup.find('title').get_text(strip=True)
        if t:
            return t
    return fallback_title

def extract_site_meta_description(soup):
    meta = soup.find('meta', attrs={'name': 'description'})
    if meta and meta.get('content'):
        return meta.get('content').strip()
    og = soup.find('meta', property='og:description')
    if og and og.get('content'):
        return og.get('content').strip()
    return ''

def extract_site_short_description(soup, fallback_raw_desc):
    node = soup.find(['div', 'p'], {'class': re.compile(r'short.?description|product[-_]?summary', re.I)})
    if node:
        text = node.get_text(' ', strip=True)
        if text and len(text) > 10:
            return text
    meta_desc = extract_site_meta_description(soup)
    if meta_desc:
        return meta_desc
    clean = re.sub(r'\s+', ' ', re.sub(r'<[^<]+?>', ' ', fallback_raw_desc or '')).strip()
    return clean[:200]

def extract_price(soup, product_data):
    price = safe_get_offer_price(product_data.get('offers'))
    if price:
        return price
    price_tag = (soup.find(attrs={'itemprop': 'price'})
                 or soup.find('meta', property='product:price:amount')
                 or soup.find('meta', attrs={'property': 'og:price:amount'}))
    if price_tag:
        val = price_tag.get('content') or price_tag.get_text(strip=True)
        match = re.search(r'[\d,]+\.?\d*', val or '')
        if match:
            return match.group()
    price_span = soup.find(['span', 'div', 'ins'], {'class': re.compile(
        r'price|amount|sale-price|regular-price|product-price|current-price', re.I)})
    if price_span:
        match = re.search(r'[\d,]+\.?\d*', price_span.get_text())
        if match:
            return match.group()
    return '0'

def extract_sku(soup, product_data):
    sku_raw = safe_get_sku(product_data.get('sku'))
    if sku_raw:
        return sku_raw
    itemprop = soup.find(attrs={'itemprop': 'sku'})
    if itemprop:
        return itemprop.get_text(strip=True) or itemprop.get('content', '')
    sku_span = (soup.find(attrs={'data-product-sku': True})
                or soup.find(['span', 'div'], {'class': re.compile(r'\bsku\b|model|product-id', re.I)}))
    if sku_span:
        text = sku_span.get('data-product-sku') or sku_span.get_text(strip=True)
        if text:
            return text
    return f"OLD-{random.randint(1000,9999)}"

def extract_vendor(soup, product_data, default="Imported Vendor"):
    brand = safe_get_brand(product_data.get('brand'))
    if brand:
        return brand
    itemprop = soup.find(attrs={'itemprop': 'brand'})
    if itemprop:
        text = itemprop.get_text(strip=True)
        if text:
            return text
    meta_brand = soup.find('meta', property='product:brand') or soup.find('meta', attrs={'name': 'author'})
    if meta_brand and meta_brand.get('content'):
        return meta_brand.get('content')
    return default

# ============================================================
# SMART TITLE GENERATOR
# ============================================================
def generate_smart_title(original_title, specs_text, color=None, material=None):
    if not specs_text:
        return original_title
    
    specs_lower = specs_text.lower()
    materials = ['leather', 'sheepskin', 'goatskin', 'cowhide', 'suede', 'nubuck', 
                 'canvas', 'denim', 'wool', 'polyester', 'nylon', 'cotton', 'hemp']
    detected_material = ''
    for mat in materials:
        if mat in specs_lower:
            detected_material = mat.capitalize()
            break
    
    finish_types = ['waxed', 'pull-up', 'semi-aniline', 'aniline', 'distressed', 
                    'vintage', 'washed', 'oiled', 'matte', 'glossy']
    detected_finish = ''
    for fin in finish_types:
        if fin in specs_lower:
            detected_finish = fin.capitalize()
            break
    
    colors = ['black', 'brown', 'tan', 'maroon', 'red', 'blue', 'green', 'grey', 
              'white', 'charcoal', 'navy', 'olive', 'camel', 'chestnut', 'mahogany']
    detected_color = ''
    for col in colors:
        if col in specs_lower:
            detected_color = col.capitalize()
            break
    
    title_parts = []
    if detected_finish:
        title_parts.append(detected_finish)
    if detected_material:
        title_parts.append(detected_material)
    
    core_name = original_title
    if detected_color and detected_color.lower() in core_name.lower():
        core_name = re.sub(re.escape(detected_color), '', core_name, flags=re.I).strip()
    if detected_material and detected_material.lower() in core_name.lower():
        core_name = re.sub(re.escape(detected_material), '', core_name, flags=re.I).strip()
    if detected_finish and detected_finish.lower() in core_name.lower():
        core_name = re.sub(re.escape(detected_finish), '', core_name, flags=re.I).strip()
    core_name = re.sub(r'\s+', ' ', core_name).strip()
    core_name = re.sub(r'-\s*', '-', core_name)
    
    if core_name:
        title_parts.append(core_name)
    else:
        title_parts.append(original_title)
    
    if detected_color and detected_color.lower() not in ' '.join(title_parts).lower():
        title_parts.append(detected_color)
    
    smart_title = ' - '.join(title_parts)
    smart_title = re.sub(r'\s+', ' ', smart_title).strip()
    smart_title = re.sub(r'-\s*-\s*', '-', smart_title)
    
    if len(smart_title) > 80:
        smart_title = smart_title[:77] + '...'
    
    return smart_title if len(smart_title) > len(original_title) * 0.5 else original_title

# ============================================================
# GALLERY IMAGE HELPERS
# ============================================================
def strip_size_suffix(url):
    try:
        clean = url.split('?')[0]
        query = url[len(clean):]
        clean = re.sub(r'(_\d{2,4}x\d{0,4})(@\d+x)?(\.[a-zA-Z]{3,4})$', r'\3', clean)
        clean = re.sub(r'(_(?:small|medium|large|thumb|thumbnail|grande|compact))(\.[a-zA-Z]{3,4})$', r'\2', clean, flags=re.I)
        return clean + query
    except Exception:
        return url

def try_get_shopify_json_images(url, session, headers):
    urls = []
    try:
        clean_url = url.split('?')[0].rstrip('/')
        if clean_url.endswith('.json'):
            json_url = clean_url
        else:
            json_url = clean_url + '.json'
        r = session.get(json_url, headers=headers, timeout=15)
        if r.status_code == 200 and 'json' in r.headers.get('Content-Type', ''):
            data = r.json()
            product = data.get('product', {})
            for img in product.get('images', []) or []:
                src = img.get('src')
                if src:
                    urls.append(src)
    except Exception:
        pass
    return urls

def extract_gallery_images_html(soup, base_url_domain):
    skip_words = ['logo', 'icon-', 'sprite', 'placeholder', 'payment', 'visa',
                  'mastercard', 'paypal', 'apple-pay', 'google-pay', 'flag-',
                  'loading.gif', 'spinner', 'avatar', 'favicon']
    attrs_to_check = ['data-zoom-image', 'data-zoom', 'data-large_image', 'data-large',
                       'data-original', 'data-lazy-src', 'data-lazy', 'data-src',
                       'data-srcset', 'srcset', 'src', 'href']

    def collect_from(tags):
        found = []
        for tag in tags:
            for attr in attrs_to_check:
                val = tag.get(attr)
                if not val:
                    continue
                if attr in ('srcset', 'data-srcset'):
                    candidates = [p.strip().split(' ')[0] for p in val.split(',') if p.strip()]
                    val = candidates[-1] if candidates else None
                if not val:
                    continue
                if attr == 'href' and not re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', val, re.I):
                    continue
                if val.startswith('//'):
                    val = 'https:' + val
                full = urljoin(base_url_domain, val)
                if not full.startswith('http') or full.lower().endswith('.svg'):
                    continue
                lower = full.lower()
                if any(word in lower for word in skip_words):
                    continue
                full = strip_size_suffix(full)
                if full not in found:
                    found.append(full)
        return found

    gallery_selectors = [
        {'class': re.compile(r'woocommerce-product-gallery', re.I)},
        {'class': re.compile(r'flex-control-thumbs', re.I)},
        {'class': re.compile(r'fotorama', re.I)},
        {'class': re.compile(r'gallery-placeholder', re.I)},
        {'data-gallery-role': True},
        {'class': re.compile(r'product[-_]?(gallery|images|media|slider|carousel)', re.I)},
        {'class': re.compile(r'swiper-wrapper|slick-track|splide__track', re.I)},
    ]
    gallery_urls = []
    for sel in gallery_selectors:
        containers = soup.find_all(['div', 'ul', 'section'], sel)
        for container in containers:
            gallery_urls.extend(collect_from(container.find_all(['img', 'source', 'a'])))

    page_urls = collect_from(soup.find_all(['img', 'source', 'a']))

    combined = []
    for url in gallery_urls + page_urls:
        if url not in combined:
            combined.append(url)
    return combined

def extract_gallery_images_from_scripts(soup, base_url_domain, exclude_urls=None):
    exclude_urls = exclude_urls or set()
    found = []
    media_hint = re.compile(r'(wp-content/uploads|media/catalog/product|cdn|assets|products|images)', re.I)
    url_pattern = re.compile(r'(https?:)?//[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?', re.I)
    for script in soup.find_all('script'):
        text = script.string or script.get_text() or ''
        if not text or len(text) > 200000:
            continue
        for match in url_pattern.finditer(text):
            val = match.group(0)
            if val.startswith('//'):
                val = 'https:' + val
            full = urljoin(base_url_domain, val)
            if not media_hint.search(full):
                continue
            full = strip_size_suffix(full)
            if full in exclude_urls or full in found:
                continue
            found.append(full)
    return found

def collect_gallery_images(url, soup, base_url_domain, session, headers, product_data, max_images):
    combined = []

    if product_data.get('image'):
        img_field = product_data['image']
        combined.extend(img_field if isinstance(img_field, list) else [img_field])

    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'):
        combined.append(og_img.get('content'))

    combined.extend(try_get_shopify_json_images(url, session, headers))
    combined.extend(extract_gallery_images_html(soup, base_url_domain))

    seen = set()
    final = []
    for img in combined:
        if not img or not img.startswith('http'):
            continue
        cleaned = strip_size_suffix(img)
        key = cleaned.split('?')[0]
        if key not in seen:
            seen.add(key)
            final.append(cleaned)
        if len(final) >= max_images:
            break

    if len(final) < 2:
        for img in extract_gallery_images_from_scripts(soup, base_url_domain, exclude_urls=seen):
            key = img.split('?')[0]
            if key not in seen:
                seen.add(key)
                final.append(img)
            if len(final) >= max_images:
                break

    return final

# ============================================================
# IMAGE EDITOR
# ============================================================
def edit_image(img_data, filename, config):
    try:
        img = Image.open(BytesIO(img_data))
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        width, height = img.size
        final_img = img

        if config.get('enable_flip', True):
            final_img = final_img.transpose(Image.FLIP_LEFT_RIGHT)
        
        if config.get('enable_enhance', True):
            enhancer = ImageEnhance.Brightness(final_img)
            final_img = enhancer.enhance(random.uniform(0.92, 1.08))
            enhancer = ImageEnhance.Contrast(final_img)
            final_img = enhancer.enhance(random.uniform(0.95, 1.05))
        
        if config.get('enable_rounded', False):
            mask = Image.new('L', final_img.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle((0, 0, width, height), radius=30, fill=255)
            final_img.putalpha(mask)
            bg = Image.new('RGB', final_img.size, (255, 255, 255))
            bg.paste(final_img, mask=final_img.split()[-1])
            final_img = bg
        
        if config.get('enable_shadow', False):
            shadow_offset = 10
            shadow_blur = 15
            shadow = Image.new('RGBA', (width + shadow_offset*2, height + shadow_offset*2), (0,0,0,0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rectangle((shadow_offset, shadow_offset, width + shadow_offset, height + shadow_offset), fill=(0,0,0,30))
            shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
            bg = Image.new('RGBA', (width + shadow_offset*2, height + shadow_offset*2), (255,255,255,0))
            bg.paste(shadow, (0,0), shadow)
            bg.paste(final_img, (shadow_offset, shadow_offset))
            final_img = bg.convert('RGB')
        
        if config.get('enable_logo', False):
            logo_bytes = config.get('corner_logo_bytes')
            if logo_bytes:
                try:
                    logo = Image.open(BytesIO(logo_bytes))
                    logo_size = (int(width * 0.15), int(height * 0.15))
                    logo.thumbnail(logo_size, Image.LANCZOS)
                    if logo.mode == 'RGBA':
                        final_img.paste(logo, (20, 20), logo)
                    else:
                        final_img.paste(logo, (20, 20))
                except:
                    pass

        if config.get('enable_watermark', False):
            opacity = config.get('watermark_opacity', 20) / 100
            wm_type = config.get('watermark_type', 'Text')
            wm_size_percent = config.get('watermark_size', 15)
            
            if final_img.mode != 'RGBA':
                final_img = final_img.convert('RGBA')
            
            watermark_layer = Image.new('RGBA', final_img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(watermark_layer)
            
            if wm_type == 'Text':
                txt = config.get('watermark_text', 'Brand')
                font_size = int(min(width, height) * (wm_size_percent / 100))
                try:
                    from PIL import ImageFont
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
                bbox = draw.textbbox((0, 0), txt, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                position = ((width - text_width) // 2, (height - text_height) // 2)
                draw.text(position, txt, font=font, fill=(255, 255, 255, int(255 * opacity)))
            else:
                wm_logo_bytes = config.get('watermark_logo_bytes')
                if wm_logo_bytes:
                    try:
                        wm_logo = Image.open(BytesIO(wm_logo_bytes))
                        target_width = int(width * (wm_size_percent / 100))
                        target_height = int(wm_logo.height * (target_width / wm_logo.width))
                        wm_logo = wm_logo.resize((target_width, target_height), Image.LANCZOS)
                        if wm_logo.mode != 'RGBA':
                            wm_logo = wm_logo.convert('RGBA')
                        alpha = wm_logo.split()[3]
                        alpha = alpha.point(lambda p: int(p * opacity))
                        wm_logo.putalpha(alpha)
                        x = (width - target_width) // 2
                        y = (height - target_height) // 2
                        watermark_layer.paste(wm_logo, (x, y), wm_logo)
                    except:
                        pass
            
            final_img = Image.alpha_composite(final_img, watermark_layer)
            final_img = final_img.convert('RGB')

        if config.get('enable_border', False):
            border_size = 10
            color = config.get('border_color', '#000000')
            final_img = ImageOps.expand(final_img, border=border_size, fill=color)
            width, height = final_img.size
        
        if config.get('enable_gradient', False):
            c1 = config.get('grad_color_1', '#FF5733')
            c2 = config.get('grad_color_2', '#33FF57')
            c1_rgb = tuple(int(c1[i:i+2], 16) for i in (1, 3, 5))
            c2_rgb = tuple(int(c2[i:i+2], 16) for i in (1, 3, 5))
            frame_height = int(height * 0.1)
            strip = Image.new('RGB', (width, frame_height))
            for x in range(width):
                ratio = x / width
                r = int(c1_rgb[0] + (c2_rgb[0] - c1_rgb[0]) * ratio)
                g = int(c1_rgb[1] + (c2_rgb[1] - c1_rgb[1]) * ratio)
                b = int(c1_rgb[2] + (c2_rgb[2] - c1_rgb[2]) * ratio)
                for y in range(frame_height):
                    strip.putpixel((x, y), (r, g, b))
            final_img.paste(strip, (0, height - frame_height))
        
        new_filename = f"branded_{int(time.time())}_{random.randint(1000,9999)}_{filename.split('/')[-1].split('?')[0]}"
        if not new_filename.lower().endswith(('.jpg', '.jpeg')):
            new_filename = new_filename.rsplit('.', 1)[0] + '.jpg'
        
        buffer = BytesIO()
        final_img.save(buffer, format='JPEG', quality=70, optimize=True)
        buffer.seek(0)
        return new_filename, buffer.getvalue()
    except Exception as e:
        try:
            new_filename = f"branded_{int(time.time())}_{random.randint(1000,9999)}_{filename.split('/')[-1].split('?')[0]}"
            if not new_filename.lower().endswith(('.jpg', '.jpeg')):
                new_filename = new_filename.rsplit('.', 1)[0] + '.jpg'
            return new_filename, img_data
        except:
            return None, None

# ============================================================
# MAIN SCRAPER (INTEGRATED WITH AI)
# ============================================================
def scrape_product(url, session, config):
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
    base_url_domain = f"{resp.url.split('/')[0]}//{resp.url.split('/')[2]}"
    product_data = {}

    def is_product_type(data_type):
        if isinstance(data_type, str):
            return data_type == 'Product'
        if isinstance(data_type, list):
            return 'Product' in data_type
        return False

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
        except Exception:
            continue
        if isinstance(data, dict) and is_product_type(data.get('@type')):
            product_data = data
            break
        graph = data.get('@graph') if isinstance(data, dict) else None
        if isinstance(graph, list):
            for entry in graph:
                if isinstance(entry, dict) and is_product_type(entry.get('@type')):
                    product_data = entry
                    break
        if product_data:
            break
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and is_product_type(entry.get('@type')):
                    product_data = entry
                    break
        if product_data:
            break

    original_title = extract_title(soup, product_data, url)
    raw_desc = extract_raw_description(soup, product_data) or original_title
    category_str = format_category(soup, product_data, original_title)
    price = extract_price(soup, product_data)
    sku_raw = extract_sku(soup, product_data)
    vendor = extract_vendor(soup, product_data)
    
    specs_text = raw_desc
    specs_section = soup.find(['div', 'ul', 'table'], {'class': re.compile(r'spec|attribute|detail|features', re.I)})
    if specs_section:
        specs_text = specs_section.get_text(' ', strip=True)
    
    # Extract color & material for smart title
    color = ''
    material = ''
    if product_data.get('color'):
        color = product_data.get('color')
    else:
        color_match = re.search(r'color[:\s]+([a-zA-Z]+)', raw_desc, re.I)
        if color_match:
            color = color_match.group(1).capitalize()
    materials = ['leather', 'sheepskin', 'goatskin', 'cowhide', 'suede', 'nubuck', 'canvas', 'denim', 'wool']
    for mat in materials:
        if mat in raw_desc.lower():
            material = mat.capitalize()
            break

    # Smart Title
    if config.get('smart_title_enabled', True):
        title = generate_smart_title(original_title, specs_text, color, material)
    else:
        title = original_title

    # ---------- AI GENERATION (New) ----------
    ai_content = None
    if config.get('ai_enabled', False) and config.get('gemini_api_key'):
        ai_content = generate_ai_description_gemini(
            title,
            specs_text,
            category_str,
            config.get('store_context', ''),
            config.get('gemini_api_key'),
            config.get('gemini_model', 'gemini-1.5-flash')
        )
    
    # Use AI content if available, else local rewriter
    rewriter = SmartRewriter()
    if ai_content:
        seo_title = ai_content.get('seo_title', f"{title} — Premium Quality")
        long_desc = ai_content.get('description_html', f"<p>{title} - Premium quality product.</p>")
        gen_seo_description = ai_content.get('seo_description', f"Shop {title} today.")
        gen_short_desc = ai_content.get('short_description', f"Discover the {title}.")
    else:
        local_content = rewriter.generate_seo_content(title, raw_desc, category_str, config.get('store_context', ''), specs_text)
        seo_title = local_content['seo_title']
        long_desc = local_content['description_html']
        gen_seo_description = local_content['seo_description']
        gen_short_desc = local_content['short_description']

    # ----- SKU -----
    rand_suffix = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=4))
    parent_sku = f"CUSTOM-{rand_suffix}-{sku_raw}"

    # ----- GALLERY IMAGES -----
    max_images = config.get('max_gallery_images', 10)
    raw_image_urls = collect_gallery_images(
        url, soup, base_url_domain, session, headers, product_data, max_images
    )

    image_zip_data = {}
    processed_image_urls = []
    
    if config.get('edit_images', False):
        for img_url in raw_image_urls:
            try:
                img_resp = session.get(img_url, timeout=15)
                if img_resp.status_code == 200:
                    new_name, edited_data = edit_image(img_resp.content, img_url, config)
                    if new_name and edited_data:
                        image_zip_data[new_name] = edited_data
                        processed_image_urls.append(new_name)
                    else:
                        processed_image_urls.append(img_url)
                else:
                    processed_image_urls.append(img_url)
            except:
                processed_image_urls.append(img_url)
    else:
        processed_image_urls = raw_image_urls
    
    main_image = processed_image_urls[0] if processed_image_urls else ''
    additional_images = processed_image_urls[1:] if len(processed_image_urls) > 1 else []

    tags = "Imported"
    handle = generate_handle(title)
    
    # ----- VARIATIONS -----
    offers = product_data.get('offers')
    variations_data = []
    
    if isinstance(offers, list) and len(offers) > 1:
        for offer in offers:
            if isinstance(offer, dict):
                var_sku = offer.get('sku', f'VAR-{len(variations_data)+1}')
                var_price = offer.get('price', price)
                var_attrs = {}
                if 'size' in offer:
                    var_attrs['Size'] = offer['size']
                if 'color' in offer:
                    var_attrs['Color'] = offer['color']
                if 'material' in offer:
                    var_attrs['Material'] = offer['material']
                if not var_attrs:
                    var_attrs['Option'] = f'Variant {len(variations_data)+1}'
                var_img = offer.get('image', '')
                variations_data.append({
                    'sku': var_sku,
                    'price': var_price,
                    'attrs': var_attrs,
                    'image': var_img
                })

    opt1_name = opt2_name = opt3_name = ''
    if variations_data:
        attr_names = set()
        for var in variations_data:
            attr_names.update(var['attrs'].keys())
        attr_names = sorted(list(attr_names))
        if len(attr_names) > 0: opt1_name = attr_names[0]
        if len(attr_names) > 1: opt2_name = attr_names[1]
        if len(attr_names) > 2: opt3_name = attr_names[2]

    # Parent Row
    parent_row = {
        'Title': title,
        'URL handle': handle,
        'Description': long_desc,
        'Vendor': vendor,
        'Product category': category_str,
        'Type': category_str.split('>')[-1].strip() if category_str and category_str != 'Uncategorized' else '',
        'Tags': tags,
        'Published on online store': 'TRUE',
        'Status': 'active',
        'SKU': '',
        'Barcode': '',
        'Option1 name': opt1_name,
        'Option1 value': '',
        'Option1 Linked To': 'Option1 name' if opt1_name else '',
        'Option2 name': opt2_name,
        'Option2 value': '',
        'Option2 Linked To': 'Option2 name' if opt2_name else '',
        'Option3 name': opt3_name,
        'Option3 value': '',
        'Option3 Linked To': 'Option3 name' if opt3_name else '',
        'Price': '',
        'Compare-at price': '',
        'Cost per item': '',
        'Charge tax': 'TRUE',
        'Tax code': '',
        'Unit price total measure': '',
        'Unit price total measure unit': '',
        'Unit price base measure': '',
        'Unit price base measure unit': '',
        'Inventory tracker': '',
        'Inventory quantity': '',
        'Continue selling when out of stock': '',
        'Weight value (grams)': '',
        'Weight unit for display': '',
        'Requires shipping': 'TRUE',
        'Fulfillment service': 'manual',
        'Product image URL': main_image,
        'Image position': '1',
        'Image alt text': title,
        'Variant image URL': '',
        'Gift card': 'FALSE',
        'SEO title': seo_title,
        'SEO description': gen_seo_description,
        'Short description': gen_short_desc,
        'Color (product.metafields.shopify.color-pattern)': '',
        'Google Shopping / Google product category': category_str,
        'Google Shopping / Gender': '',
        'Google Shopping / Age group': '',
        'Google Shopping / Manufacturer part number (MPN)': '',
        'Google Shopping / Ad group name': '',
        'Google Shopping / Ads labels': '',
        'Google Shopping / Condition': '',
        'Google Shopping / Custom product': '',
        'Google Shopping / Custom label 0': '',
        'Google Shopping / Custom label 1': '',
        'Google Shopping / Custom label 2': '',
        'Google Shopping / Custom label 3': '',
        'Google Shopping / Custom label 4': ''
    }

    # Additional Image Rows
    image_rows = []
    for idx, img_url in enumerate(additional_images, start=2):
        img_row = {col: '' for col in SHOPIFY_COLUMNS}
        img_row['URL handle'] = handle
        img_row['Product image URL'] = img_url
        img_row['Image position'] = str(idx)
        image_rows.append(img_row)

    # Variant Rows
    variant_rows = []
    if variations_data:
        for idx, var in enumerate(variations_data):
            var_sku = f"{parent_sku}-{var.get('sku', random.randint(100,999))}"
            var_price = var.get('price', price)
            var_attrs = var['attrs']
            attr1_val = list(var_attrs.values())[0] if len(var_attrs) > 0 else ''
            attr2_val = list(var_attrs.values())[1] if len(var_attrs) > 1 else ''
            attr3_val = list(var_attrs.values())[2] if len(var_attrs) > 2 else ''

            var_img = var.get('image', '')
            var_img_url = ''
            if config.get('edit_images', False) and var_img:
                try:
                    img_resp = session.get(var_img, timeout=15)
                    if img_resp.status_code == 200:
                        new_name, edited_data = edit_image(img_resp.content, var_img, config)
                        if new_name and edited_data:
                            image_zip_data[new_name] = edited_data
                            var_img_url = new_name
                except:
                    var_img_url = var_img
            if not var_img_url:
                var_img_url = ''

            variant_row = {
                'Title': '',
                'URL handle': handle,
                'Description': '',
                'Vendor': '',
                'Product category': '',
                'Type': '',
                'Tags': '',
                'Published on online store': 'TRUE',
                'Status': 'active',
                'SKU': var_sku,
                'Barcode': random.randint(1000000000, 9999999999),
                'Option1 name': '',
                'Option1 value': attr1_val,
                'Option1 Linked To': '',
                'Option2 name': '',
                'Option2 value': attr2_val,
                'Option2 Linked To': '',
                'Option3 name': '',
                'Option3 value': attr3_val,
                'Option3 Linked To': '',
                'Price': var_price,
                'Compare-at price': '',
                'Cost per item': '',
                'Charge tax': 'TRUE',
                'Tax code': '',
                'Unit price total measure': '',
                'Unit price total measure unit': '',
                'Unit price base measure': '',
                'Unit price base measure unit': '',
                'Inventory tracker': 'shopify',
                'Inventory quantity': 10,
                'Continue selling when out of stock': 'DENY',
                'Weight value (grams)': 150,
                'Weight unit for display': 'g',
                'Requires shipping': 'TRUE',
                'Fulfillment service': 'manual',
                'Product image URL': '',
                'Image position': '',
                'Image alt text': '',
                'Variant image URL': var_img_url,
                'Gift card': 'FALSE',
                'SEO title': '',
                'SEO description': '',
                'Color (product.metafields.shopify.color-pattern)': attr2_val if opt2_name.lower() == 'color' else attr1_val if opt1_name.lower() == 'color' else '',
                'Google Shopping / Google product category': '',
                'Google Shopping / Gender': '',
                'Google Shopping / Age group': '',
                'Google Shopping / Manufacturer part number (MPN)': f'MPN-{var_sku}',
                'Google Shopping / Ad group name': '',
                'Google Shopping / Ads labels': '',
                'Google Shopping / Condition': 'New',
                'Google Shopping / Custom product': '',
                'Google Shopping / Custom label 0': '',
                'Google Shopping / Custom label 1': '',
                'Google Shopping / Custom label 2': '',
                'Google Shopping / Custom label 3': '',
                'Google Shopping / Custom label 4': ''
            }
            variant_rows.append(variant_row)
    
    if not variations_data:
        parent_row['SKU'] = parent_sku
        parent_row['Price'] = price
        parent_row['Inventory tracker'] = 'shopify'
        parent_row['Inventory quantity'] = 10
        parent_row['Continue selling when out of stock'] = 'DENY'
        parent_row['Weight value (grams)'] = 150
        parent_row['Weight unit for display'] = 'g'
        parent_row['Fulfillment service'] = 'manual'
        parent_row['Barcode'] = random.randint(1000000000, 9999999999)

    final_rows = [parent_row] + image_rows + variant_rows
    return final_rows, image_zip_data, None

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/126.0',
]

SHOPIFY_COLUMNS = [
    'Title', 'URL handle', 'Description', 'Vendor', 'Product category', 'Type', 'Tags',
    'Published on online store', 'Status', 'SKU', 'Barcode', 'Option1 name',
    'Option1 value', 'Option1 Linked To', 'Option2 name', 'Option2 value',
    'Option2 Linked To', 'Option3 name', 'Option3 value', 'Option3 Linked To',
    'Price', 'Compare-at price', 'Cost per item', 'Charge tax', 'Tax code',
    'Unit price total measure', 'Unit price total measure unit',
    'Unit price base measure', 'Unit price base measure unit', 'Inventory tracker',
    'Inventory quantity', 'Continue selling when out of stock',
    'Weight value (grams)', 'Weight unit for display', 'Requires shipping',
    'Fulfillment service', 'Product image URL', 'Image position', 'Image alt text',
    'Variant image URL', 'Gift card', 'SEO title', 'SEO description',
    'Color (product.metafields.shopify.color-pattern)',
    'Google Shopping / Google product category', 'Google Shopping / Gender',
    'Google Shopping / Age group', 'Google Shopping / Manufacturer part number (MPN)',
    'Google Shopping / Ad group name', 'Google Shopping / Ads labels',
    'Google Shopping / Condition', 'Google Shopping / Custom product',
    'Google Shopping / Custom label 0', 'Google Shopping / Custom label 1',
    'Google Shopping / Custom label 2', 'Google Shopping / Custom label 3',
    'Google Shopping / Custom label 4'
]

WOOCOMMERCE_COLUMNS = [
    'ID', 'Type', 'SKU', 'Name', 'Published', 'Is featured?', 'Visibility in catalog',
    'Short description', 'Description', 'Date sale price starts', 'Date sale price ends',
    'Tax status', 'Tax class', 'In stock?', 'Stock', 'Low stock amount',
    'Backorders allowed?', 'Sold individually?', 'Weight (kg)', 'Length (cm)',
    'Width (cm)', 'Height (cm)', 'Allow customer reviews?', 'Purchase note',
    'Sale price', 'Regular price', 'Categories', 'Tags', 'Shipping class', 'Images',
    'Download limit', 'Download expiry days', 'Parent', 'Grouped products',
    'Upsells', 'Cross-sells', 'External URL', 'Button text', 'Position',
    'Attribute 1 name', 'Attribute 1 value(s)', 'Attribute 1 visible', 'Attribute 1 global',
    'Attribute 2 name', 'Attribute 2 value(s)', 'Attribute 2 visible', 'Attribute 2 global',
    'Attribute 3 name', 'Attribute 3 value(s)', 'Attribute 3 visible', 'Attribute 3 global',
    'Meta: _yoast_wpseo_title', 'Meta: _yoast_wpseo_metadesc'
]

def group_rows_by_product(all_rows):
    groups = []
    current = []
    for row in all_rows:
        if row.get('Title'):
            if current:
                groups.append(current)
            current = [row]
        else:
            if current:
                current.append(row)
    if current:
        groups.append(current)
    return groups

def build_woocommerce_rows(product_rows, config):
    if not product_rows:
        return []

    parent = product_rows[0]
    handle = parent.get('URL handle', '')

    images = [parent.get('Product image URL', '')] if parent.get('Product image URL') else []
    variant_rows_src = []
    for r in product_rows[1:]:
        if not r.get('SKU') and r.get('Product image URL'):
            images.append(r['Product image URL'])
        elif r.get('SKU'):
            variant_rows_src.append(r)
    images_str = ', '.join([img for img in images if img])

    has_variants = len(variant_rows_src) > 0

    attr1_name = parent.get('Option1 name', '')
    attr2_name = parent.get('Option2 name', '')
    attr3_name = parent.get('Option3 name', '')
    attr1_vals = sorted({r['Option1 value'] for r in variant_rows_src if r.get('Option1 value')}) if attr1_name else []
    attr2_vals = sorted({r['Option2 value'] for r in variant_rows_src if r.get('Option2 value')}) if attr2_name else []
    attr3_vals = sorted({r['Option3 value'] for r in variant_rows_src if r.get('Option3 value')}) if attr3_name else []

    woo_parent = {col: '' for col in WOOCOMMERCE_COLUMNS}
    woo_parent.update({
        'Type': 'variable' if has_variants else 'simple',
        'SKU': parent.get('SKU', ''),
        'Name': parent.get('Title', ''),
        'Published': '1' if parent.get('Published on online store') == 'TRUE' else '0',
        'Is featured?': '0',
        'Visibility in catalog': 'visible',
        'Short description': parent.get('Short description', ''),
        'Description': parent.get('Description', ''),
        'Tax status': 'taxable' if parent.get('Charge tax') == 'TRUE' else 'none',
        'In stock?': '1',
        'Stock': parent.get('Inventory quantity', ''),
        'Backorders allowed?': '0' if parent.get('Continue selling when out of stock') == 'DENY' else '1',
        'Weight (kg)': parent.get('Weight value (grams)', ''),
        'Allow customer reviews?': '1',
        'Regular price': '' if has_variants else parent.get('Price', ''),
        'Categories': parent.get('Product category', ''),
        'Tags': parent.get('Tags', ''),
        'Images': images_str,
        'Attribute 1 name': attr1_name,
        'Attribute 1 value(s)': ', '.join(attr1_vals),
        'Attribute 1 visible': '1' if attr1_name else '',
        'Attribute 1 global': '0',
        'Attribute 2 name': attr2_name,
        'Attribute 2 value(s)': ', '.join(attr2_vals),
        'Attribute 2 visible': '1' if attr2_name else '',
        'Attribute 2 global': '0',
        'Attribute 3 name': attr3_name,
        'Attribute 3 value(s)': ', '.join(attr3_vals),
        'Attribute 3 visible': '1' if attr3_name else '',
        'Attribute 3 global': '0',
        'Meta: _yoast_wpseo_title': parent.get('SEO title', ''),
        'Meta: _yoast_wpseo_metadesc': parent.get('SEO description', ''),
    })

    rows = [woo_parent]
    if has_variants:
        for r in variant_rows_src:
            woo_var = {col: '' for col in WOOCOMMERCE_COLUMNS}
            woo_var.update({
                'Type': 'variation',
                'SKU': r.get('SKU', ''),
                'Name': f"{parent.get('Title', '')} - Variation",
                'Published': '1',
                'Visibility in catalog': 'visible',
                'Tax status': 'taxable' if r.get('Charge tax') == 'TRUE' else 'none',
                'In stock?': '1',
                'Stock': r.get('Inventory quantity', ''),
                'Backorders allowed?': '0' if r.get('Continue selling when out of stock') == 'DENY' else '1',
                'Weight (kg)': r.get('Weight value (grams)', ''),
                'Regular price': r.get('Price', ''),
                'Images': r.get('Variant image URL', ''),
                'Parent': handle,
                'Attribute 1 name': attr1_name,
                'Attribute 1 value(s)': r.get('Option1 value', ''),
                'Attribute 2 name': attr2_name,
                'Attribute 2 value(s)': r.get('Option2 value', ''),
                'Attribute 3 name': attr3_name,
                'Attribute 3 value(s)': r.get('Option3 value', ''),
            })
            rows.append(woo_var)
    return rows

# ============================================================
# PROCESS BATCH FUNCTION
# ============================================================
def process_batch(urls, config, session):
    all_rows = []
    image_data = {}
    failed = []
    for url in urls:
        results, img_data, error = scrape_product(url, session, config)
        if results:
            all_rows.extend(results)
            if img_data:
                image_data.update(img_data)
        else:
            failed.append(url)
    return all_rows, image_data, failed

# ============================================================
# START / RESUME PROCESSING
# ============================================================
if st.button("🚀 Generate Shopify CSV + ZIP (Batch Mode)", type="primary") or st.session_state.is_processing:
    
    if not st.session_state.is_processing and urls_input.strip():
        urls_list = [u.strip() for u in re.split(r'[,\s]+', urls_input) if u.strip().startswith('http')]
        if not urls_list:
            st.error("❌ Valid URL nahi mili.")
        else:
            st.session_state.total_urls = len(urls_list)
            st.session_state.all_urls = urls_list
            st.session_state.batch_index = 0
            st.session_state.all_final_rows = []
            st.session_state.all_image_data = {}
            st.session_state.all_failed = []
            st.session_state.is_processing = True
            st.rerun()
    
    if st.session_state.is_processing:
        urls_list = st.session_state.all_urls
        batch_idx = st.session_state.batch_index
        total = st.session_state.total_urls
        
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, total)
        current_batch = urls_list[start:end]
        
        if start < total:
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            status_text.info(f"⏳ Processing Batch {batch_idx+1}/{(total // BATCH_SIZE) + 1} ({start+1} to {end} of {total})...")
            
            config = get_branding_config()
            session = requests.Session()

            batch_rows, batch_images, batch_failed = process_batch(current_batch, config, session)
            
            st.session_state.all_final_rows.extend(batch_rows)
            st.session_state.all_image_data.update(batch_images)
            st.session_state.all_failed.extend(batch_failed)
            st.session_state.batch_index += 1
            
            progress_bar.progress(1.0)
            status_text.success(f"✅ Batch {batch_idx+1} complete. Total rows so far: {len(st.session_state.all_final_rows)}")
            
            if st.session_state.batch_index * BATCH_SIZE < total:
                time.sleep(2)
                st.rerun()
            else:
                st.session_state.is_processing = False

                if base_url:
                    for row in st.session_state.all_final_rows:
                        for col in ['Product image URL', 'Variant image URL']:
                            img_col = row.get(col, '')
                            if img_col:
                                imgs = img_col.split(', ')
                                new_imgs = []
                                for img in imgs:
                                    if not img.startswith('http'):
                                        new_imgs.append(f"{base_url.rstrip('/')}/{img.lstrip('/')}")
                                    else:
                                        new_imgs.append(img)
                                row[col] = ', '.join(new_imgs)

                config = get_branding_config()
                if config.get('export_format') == 'woocommerce':
                    product_groups = group_rows_by_product(st.session_state.all_final_rows)
                    woo_rows = []
                    for group in product_groups:
                        woo_rows.extend(build_woocommerce_rows(group, config))
                    df = pd.DataFrame(woo_rows, columns=WOOCOMMERCE_COLUMNS)
                    for col in WOOCOMMERCE_COLUMNS:
                        if col not in df.columns: df[col] = ''
                    df = df[WOOCOMMERCE_COLUMNS]
                else:
                    df = pd.DataFrame(st.session_state.all_final_rows, columns=SHOPIFY_COLUMNS)
                    for col in SHOPIFY_COLUMNS:
                        if col not in df.columns: df[col] = ''
                    df = df[SHOPIFY_COLUMNS]

                csv_buffer = StringIO()
                df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                csv_data = csv_buffer.getvalue()

                st.session_state.csv_data = csv_data
                st.session_state.df_preview = df
                st.session_state.failed_urls = st.session_state.all_failed
                st.session_state.total_rows = len(st.session_state.all_final_rows)
                st.session_state.is_ready = True
                
                st.session_state.has_zip = False
                st.session_state.zip_data = None
                
                st.rerun()
        else:
            st.session_state.is_processing = False

# ============================================================
# DISPLAY DOWNLOAD SECTION
# ============================================================
if st.session_state.is_ready:
    st.success(f"🎯 {st.session_state.total_rows} rows generated! {len(st.session_state.failed_urls)} failed.")
    if st.session_state.failed_urls:
        with st.expander(f"⚠️ Show {len(st.session_state.failed_urls)} Failed URLs"):
            st.write('\n'.join(st.session_state.failed_urls))
    
    st.subheader("📊 Preview (First 10 rows)")
    st.dataframe(st.session_state.df_preview.head(10))
    
    col_a, col_b, col_c = st.columns([2, 2, 1])
    
    with col_a:
        is_woo = st.session_state.get("export_format", "🛍️ Shopify CSV").startswith("🛒")
        st.download_button(
            label=f"⬇️ Download {'WooCommerce' if is_woo else 'Shopify'} CSV",
            data=st.session_state.csv_data,
            file_name=f"{'woocommerce_import' if is_woo else 'shopify_import'}_{int(time.time())}.csv",
            mime="text/csv",
            use_container_width=True,
            key="csv_download"
        )
    
    with col_b:
        if st.session_state.has_zip and st.session_state.zip_data:
            zip_size_mb = len(st.session_state.zip_data) / (1024 * 1024)
            if zip_size_mb > 800:
                st.warning(f"⚠️ ZIP size is {zip_size_mb:.1f} MB. Download might be slow.")
            st.download_button(
                label=f"⬇️ Download Images ZIP ({zip_size_mb:.1f} MB)",
                data=st.session_state.zip_data,
                file_name=f"branded_images_{int(time.time())}.zip",
                mime="application/zip",
                use_container_width=True,
                key="zip_download"
            )
        else:
            if st.button("🔄 Generate ZIP (Images)", use_container_width=True):
                with st.spinner("📦 ZIP file prepare ho rahi hai... (Large files may take 3-5 min)"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i in range(101):
                        if i % 20 == 0:
                            status_text.text(f"⏳ Compressing images... {i}%")
                        progress_bar.progress(i / 100)
                        time.sleep(0.05)
                    
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for fname, fdata in st.session_state.all_image_data.items():
                            zf.writestr(fname, fdata)
                    zip_buffer.seek(0)
                    zip_ready = zip_buffer.getvalue()
                    
                    zip_size_mb = len(zip_ready) / (1024 * 1024)
                    if zip_size_mb > 1000:
                        st.error(f"❌ ZIP file {zip_size_mb:.1f} MB ki ho gayi! (Limit: 1000 MB)")
                        st.warning("⚠️ Itni badi ZIP file server memory ko exceed kar sakti hai. Please process max 300-400 URLs at a time.")
                    else:
                        st.session_state.zip_data = zip_ready
                        st.session_state.has_zip = True
                        progress_bar.progress(1.0)
                        status_text.text("✅ ZIP ready!")
                        st.rerun()
                
            st.info("ℹ️ Click 'Generate ZIP' to prepare images for download.")
    
    with col_c:
        if st.button("🔄 Reset & New Batch", use_container_width=True):
            for key in ['is_ready', 'csv_data', 'zip_data', 'df_preview', 'failed_urls', 'total_rows', 'has_zip',
                        'batch_index', 'all_final_rows', 'all_image_data', 'all_failed', 'total_urls', 'is_processing', 'all_urls']:
                if key in st.session_state:
                    if key in ['total_rows', 'batch_index', 'total_urls']:
                        st.session_state[key] = 0
                    elif key in ['failed_urls', 'all_failed']:
                        st.session_state[key] = []
                    elif key in ['all_image_data']:
                        st.session_state[key] = {}
                    elif key in ['all_final_rows']:
                        st.session_state[key] = []
                    elif key in ['is_ready', 'has_zip', 'is_processing']:
                        st.session_state[key] = False
                    else:
                        st.session_state[key] = None
            st.rerun()

st.caption("🛒 V5.1 | Gemini AI Descriptions (Toggle) | Smart Titles | Bullet Specs | Variations Fixed | 1000 MB ZIP Limit")
