"""
erp_adapter.py — ERP Entegrasyon Katmanı
Bu modül, AI ve Parser tarafından üretilen standart Canonical Data Model'i (CDM) alır,
hedef ERP sistemlerinin (1C, Netsis, Logo vb.) anlayacağı XML veya JSON yapılarına dönüştürür.
"""

import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime
import os

class CanonicalDataModel:
    """Tüm banka işlemlerinin standartlaşmış veri yapısı (Data Contract)"""
    def __init__(self, row: pd.Series):
        self.tarih = str(row.get("islem_tarihi", ""))
        self.fis_no = str(row.get("fis_no", ""))
        self.islem_yonu = str(row.get("islem_yonu", ""))
        self.islem_tipi = str(row.get("islem_tipi", "BELİRSİZ"))
        self.karsitaraf_ad = str(row.get("karsitaraf_ad", ""))
        self.karsitaraf_iban = str(row.get("karsitaraf_iban", ""))
        self.aciklama_temiz = str(row.get("aciklama_temiz", ""))
        self.muhasebe_hesabi = str(row.get("muhasebe_hesabi", ""))
        self.cari_durumu = str(row.get("cari_durumu", ""))

class ERPAdapter1C:
    """1C Enterprise ERP sistemi için XML dönüştürücü."""
    
    def __init__(self, sirket_kodu: str = "COMP01"):
        self.sirket_kodu = sirket_kodu
        self.olusturma_tarihi = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def convert_to_xml(self, dataframe: pd.DataFrame, output_path: str):
        """Canonical DataFrame'i 1C XML yapısına dönüştürür."""
        
        # XML Kök Elemanı
        root = ET.Element("Message1C")
        root.set("version", "1.0")
        root.set("creationDate", self.olusturma_tarihi)
        
        header = ET.SubElement(root, "Header")
        ET.SubElement(header, "CompanyCode").text = self.sirket_kodu
        ET.SubElement(header, "DocumentType").text = "BankStatement"
        
        transactions = ET.SubElement(root, "Transactions")
        
        for index, row in dataframe.iterrows():
            cdm = CanonicalDataModel(row)
            
            # Her bir banka işlemi için Transaction düğümü
            txn = ET.SubElement(transactions, "Transaction")
            
            # Ana Bilgiler
            ET.SubElement(txn, "Date").text = cdm.tarih
            ET.SubElement(txn, "DocumentNo").text = cdm.fis_no
            ET.SubElement(txn, "Direction").text = cdm.islem_yonu # GİRİŞ / ÇIKIŞ
            ET.SubElement(txn, "TransactionType").text = cdm.islem_tipi
            
            # Muhasebe (Etap 3 için alt yapı)
            accounting = ET.SubElement(txn, "Accounting")
            ET.SubElement(accounting, "SuggestedAccountCode").text = cdm.muhasebe_hesabi
            ET.SubElement(accounting, "CariStatus").text = cdm.cari_durumu
            
            # Karşı Taraf (Cari) Bilgileri
            counterparty = ET.SubElement(txn, "Counterparty")
            ET.SubElement(counterparty, "Name").text = cdm.karsitaraf_ad
            ET.SubElement(counterparty, "IBAN").text = cdm.karsitaraf_iban
            
            # Açıklama
            ET.SubElement(txn, "Description").text = cdm.aciklama_temiz

        # XML Ağacını kaydet
        tree = ET.ElementTree(root)
        ET.indent(tree, space="    ", level=0)  # Python 3.9+ için pretty print
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        return output_path

# Test bloğu
if __name__ == "__main__":
    # Eğer parser başarıyla çalışmışsa oluşan dosyayı alıp XML'e çevir
    excel_path = r"C:\Users\HUAWEİ\Downloads\Hesap_Hareketleri_PARSED.xlsx"
    xml_output = r"C:\Users\HUAWEİ\Downloads\Hesap_Hareketleri_1C_Aktarim.xml"
    
    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path)
        # NaN ve Null değerleri string'e çevir
        df = df.fillna("")
        adapter = ERPAdapter1C()
        adapter.convert_to_xml(df, xml_output)
        print(f"Başarılı! 1C XML dosyası oluşturuldu: {xml_output}")
    else:
        print(f"Hata: {excel_path} bulunamadı. Önce parse_ekstre.py'yi çalıştırın.")
