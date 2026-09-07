from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import json
import random

# --- ΡΥΘΜΙΣΕΙΣ ---
INPUT_FILE = 'data/urls.txt'
OUTPUT_FILE = 'data/real_products_data.json'

print(f"Διαβάζω τα links από το {INPUT_FILE}...")

try:
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        product_urls = [line.strip() for line in f if line.strip()]
    print(f"Βρέθηκαν {len(product_urls)} προϊόντα.")
except FileNotFoundError:
    print(f"Δεν βρέθηκε το αρχείο {INPUT_FILE}!")
    product_urls = []

# Εκκίνηση Browser
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
# Απενεργοποίηση κάποιων automation flags (αποφυγη μπλοκαρισμων)
options.add_argument("--disable-blink-features=AutomationControlled") 
options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
options.add_experimental_option("useAutomationExtension", False) 

if product_urls:
    print("Εκκίνηση του Chrome Driver...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # --- ΒΗΜΑ 1: ΧΕΙΡΟΚΙΝΗΤΗ ΕΙΣΟΔΟΣ ---
    print("\n" + "="*60)
    print("ΣΤΟΠ! Ο Browser άνοιξε.")
    print("Πήγαινε στο παράθυρο του Chrome.")
    print("Αν σου έβγαλε CAPTCHA, λύσε το.")
    print("Καλύτερα: Κάνε LOGIN στον λογαριασμό σου στο Skroutz (βοηθάει πολύ!).")
    print("Μόλις είσαι έτοιμος και βλέπεις κανονικά τη σελίδα, έλα εδώ και ΠΑΤΑ ENTER.")
    print("="*60 + "\n")
    
    # Πηγαίνουμε στην αρχική για να κάνεις login/captcha
    driver.get("https://www.skroutz.gr") 
    input("Πάτα ENTER εδώ όταν είσαι έτοιμος να ξεκινήσεις...")

    data_list = []

    try:
        for i, url in enumerate(product_urls):
            print(f"\n[{i+1}/{len(product_urls)}] 🔄 Μετάβαση: {url[:50]}...")
            
            driver.get(url)
            
            # Έλεγχος αν πετάχτηκε CAPTCHA
            if "robot" in driver.title or "επιβεβαίωση" in driver.title or "Just a moment" in driver.title:
                print("\nΕΝΤΟΠΙΣΤΗΚΕ CAPTCHA")
                import winsound; winsound.Beep(1000, 500) # Κάνει ήχο μπιπ
                print("Λύσε το CAPTCHA στον Chrome και μετά πάτα ENTER εδώ για να συνεχίσω...")
                input() # Περιμένει να πατήσεις Enter
            
            # Τυχαία αναμονή
            time.sleep(random.uniform(5, 8))
            
            # Scroll
            driver.execute_script("window.scrollTo(0, 800);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, 1600);")
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Τίτλος
            title_tag = soup.find("meta", property="og:title")
            title = title_tag["content"] if title_tag else "N/A"
            
            # Αν δεν φόρτωσε
            if title == "N/A":
                print("Η σελίδα δεν φόρτωσε σωστά. (Δοκίμασε να αυξήσεις το χρόνο αναμονής)")
                # Εδώ δίνουμε άλλη μια ευκαιρία στο χρήστη αν θέλει να δει τι έγινε
                # input("Πάτα Enter για να προσπεράσω αυτό το προϊόν...") 
                continue

            # Τιμή
            #price_tag = soup.find("meta", attrs={"name": "twitter:data1"})
            #price = price_tag["content"].replace(" €", "").replace(",", ".") if price_tag else "0.0"
            price = "0.0"
            
            # Plan A: Ψάχνει το παλιό twitter tag
            price_tag_1 = soup.find("meta", attrs={"name": "twitter:data1"})
            # Plan B: Ψάχνει το νέο στάνταρ SEO tag (product:price:amount)
            price_tag_2 = soup.find("meta", property="product:price:amount")
            # Plan C: Ψάχνει το κλασικό tag (itemprop="price")
            price_tag_3 = soup.find(attrs={"itemprop": "price"})
            
            if price_tag_1 and "content" in price_tag_1.attrs:
                price = price_tag_1["content"].replace(" €", "").replace(",", ".")
            elif price_tag_2 and "content" in price_tag_2.attrs:
                price = price_tag_2["content"].replace(",", ".")
            elif price_tag_3 and "content" in price_tag_3.attrs:
                price = price_tag_3["content"].replace(",", ".")

            # Κατηγορία
            category = "N/A"
            
            # Plan A: Το παλιό meta tag
            cat_tag_1 = soup.find("meta", itemprop="category")
            # Plan B: Εναλλακτικό meta tag
            cat_tag_2 = soup.find("meta", property="product:category")
            
            if cat_tag_1 and "content" in cat_tag_1.attrs:
                category = cat_tag_1["content"]
            elif cat_tag_2 and "content" in cat_tag_2.attrs:
                category = cat_tag_2["content"]
            else:
                # Plan C: Διάβασμα από τα Breadcrumbs (τη διαδρομή σελίδας)
                # Βρίσκει όλα τα στοιχεία της διαδρομής
                breadcrumbs = soup.find_all("li", itemprop="itemListElement")
                if breadcrumbs and len(breadcrumbs) >= 2:
                    # Το τελευταίο [ -1 ] είναι το όνομα του προϊόντος, το προτελευταίο [ -2 ] είναι η κατηγορία
                    category = breadcrumbs[-2].text.strip()
                elif breadcrumbs:
                    category = breadcrumbs[-1].text.strip()

            # Κατηγορία & Εικόνα
            #cat_tag = soup.find("meta", itemprop="category")
            #category = cat_tag["content"] if cat_tag else "N/A"
            img_tag = soup.find("meta", property="og:image")
            image = img_tag["content"] if img_tag else ""

            # Specs
            specs_data = {}
            specs_container = soup.find('div', id='specs')
            if specs_container:
                groups = specs_container.find_all('div', class_='spec-details')
                for group in groups:
                    group_name = group.h3.text.strip() if group.h3 else "General"
                    dls = group.find_all('dl')
                    for dl in dls:
                        key = dl.dt.text.strip()
                        val = dl.dd.text.strip()
                        specs_data[f"{group_name} - {key}"] = val

            print(f"Επιτυχία: {title[:30]}... | Specs: {len(specs_data)}")

            data_list.append({
                "name": title,
                "price": float(price) if price.replace('.', '', 1).isdigit() else 0.0,
                "category": category,
                "image": image,
                "url": url,
                "specs": specs_data
            })

    except Exception as e:
        print(f"Σφάλμα: {e}")

    finally:
        print("Κλείσιμο Browser...")
        driver.quit()

    if data_list:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=4)
        print(f"\nΟΛΟΚΛΗΡΩΘΗΚΕ! {len(data_list)} προϊόντα αποθηκεύτηκαν.")
else:
    print("Κενή λίστα URLs.")