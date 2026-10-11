# Havada Çizim

Kameradaki el hareketlerini kullanarak ekranda çizim yap. Çizmek için başparmak ve işaret parmağını birleştirip elini hareket ettir; fare veya kalem gerekmez.

![Havada çizim uygulamasında yapılmış örnek çizim](cizim_1791488818.png)

## Özellikler

- Başparmak ve işaret parmağıyla çizim ve panel kontrolleri
- Renk tonu, doygunluk ve parlaklık seçimi
- Fırça kalınlığı ayarı ve imleçte fırça önizlemesi
- Silgi, temizleme, geri alma (en fazla 20 kayıt) ve PNG olarak kaydetme
- Çizimi dikey eksene göre aynalama
- İsteğe bağlı çizgi, daire, elips, üçgen ve dörtgen tanıma
- İmleç konumu için One Euro filtresiyle titreşim azaltma

Şekil tanıma açıkken tanınmayan çizimler serbest çizim olarak kalır. Kalp ve yıldız gibi içe girintili şekiller özellikle otomatik şekle dönüştürülmez.

## Gereksinimler

- Python ve `requirements.txt` içindeki paketlerle uyumlu bir Python sürümü
- Çalışan bir kamera
- El modeli ilk kez indirilirken internet bağlantısı

Paketlerin uyumlu olduğu Python sürümü, kullandığınız Python dağıtımına ve paket sürümlerine bağlıdır. Bu projede paket sürümleri sabitlenmediğinden belirli bir Python sürümünün test edildiği garanti edilmez.

## Kurulum ve çalıştırma

Komutları proje klasöründe çalıştırın:

```bash
git clone https://github.com/ey7025992-rgb/havada-cizim..git havada-cizim
cd havada-cizim
python -m venv .venv
```

Sanal ortamı etkinleştirin.

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
source .venv/bin/activate
```

Ardından bağımlılıkları kurup uygulamayı başlatın:

```bash
python -m pip install -r requirements.txt
python havada_cizim.py
```

İlk çalıştırmada MediaPipe el modeli olan `hand_landmarker.task` yaklaşık 8 MB boyutunda indirilir. İndirme için internet bağlantısı gerekir. Model ve kaydedilen çizimler, uygulamayı başlattığınız geçerli klasöre yazılır; bu nedenle komutları proje klasöründe çalıştırın.

## Kullanım

Uygulama penceresinde elinizi kameranın görebileceği şekilde tutun.

| El hareketi | Sonuç |
|---|---|
| El algılanırken başparmak ve işaret parmağı ayrı | Çizim yapmaz; ekranda imleç ve parmak uçları arasındaki çizgi görünür |
| Başparmak ve işaret parmağı birleşik | İmlecin bulunduğu tuvalde çizer veya panelde bir kontrolü seçip sürükler |

Çizim, el ilk algılandığında kendiliğinden başlamaz; çizmek için parmakları birleştirmek gerekir. El algılanmaya başladığı anda parmaklar zaten birleşikse çizim başlayabilir.

### Sağ panel

- **RENK çubuğu:** Renk tonunu seçer.
- **Renk karesi:** Seçilen tonun doygunluğunu ve parlaklığını ayarlar.
- **KALINLIK çubuğu:** Fırça boyutunu ayarlar (2–60).
- **SILGI:** Silgiyi açıp kapatır.
- **GERI AL:** Son çizim/temizleme işlemlerinden birini geri alır; geçmiş en fazla 20 kayıt tutar.
- **TEMIZLE:** Tuvali temizler.
- **KAYDET:** Tuvali beyaz arka planlı PNG olarak kaydeder.
- **SIMETRI:** Aynalama modunu açıp kapatır.
- **SEKIL:** Şekil tanımayı açıp kapatır.

Panelde bir çubuğu ayarlamak için tutam yapıp imleci çubuk üzerinde sürükleyin. Bir butonu kullanmak için butonun üzerinde tutam yapın.

### Klavye tuşları

Kodda aşağıdaki tuşlar tanımlıdır. Tuşları **Havada Cizim** penceresi odaktayken basın; terminal penceresi odaktaysa tuşlar uygulamaya ulaşmayabilir.

| Tuş | İşlev |
|---|---|
| `q` | Uygulamadan çıkar |
| `s` | Çizimi `cizim_<zaman>.png` adıyla kaydeder |
| `c` | Tuvali temizler |
| `z` | Geri alır |
| `m` | Simetri modunu açar/kapatır |
| `t` | Şekil tanımayı açar/kapatır |

Klavye tuşları tepki vermiyorsa önce uygulama penceresine tıklayıp odağı verin. Kaydetme, temizleme, geri alma, simetri ve şekil tanıma işlemleri sağ paneldeki butonlardan da yapılabilir.

## Ayarlar

`havada_cizim.py` dosyasının başındaki **AYARLAR** bölümünden değiştirilebilir:

| Değişken | Etkisi |
|---|---|
| `W`, `H` | Uygulama görüntüsünün genişliğini ve yüksekliğini belirler |
| `PINCH_AC` | Parmaklar ayrı durumdayken tutamı başlatma eşiği; artırmak tutamı başlatmayı kolaylaştırır |
| `PINCH_BIRAK` | Aktif tutamı bırakma eşiği |
| `MIN_BOYUT`, `MAX_BOYUT` | Ayarlanabilir fırça kalınlığının alt ve üst sınırları |
| `TITREME_MIN`, `TITREME_BETA` | One Euro filtresinin yumuşatma ve harekete tepki ayarları |

`PINCH_AC` ve `PINCH_BIRAK` birlikte çalışır; tutam başlatma/bırakma davranışını ayarlarken ikisini de dikkate alın. `TITREME_MIN` değerini düşürmek daha fazla yumuşatma sağlar, ancak hareketin daha gecikmeli hissedilmesine neden olabilir.

## Sorun giderme

- **Kamera görüntüsü gelmiyor:** Kod varsayılan olarak `cv2.VideoCapture(0)` kamera indeksini kullanır. Başka kamera kullanıyorsanız bu değeri `1` gibi uygun kamera numarasıyla değiştirin.
- **`ModuleNotFoundError` veya paket kurulumu başarısız:** Sanal ortamın etkin olduğundan emin olun ve `python -m pip install -r requirements.txt` komutunu uygulamayı çalıştırdığınız Python ile çalıştırın. Python sürümünüzün MediaPipe ve diğer paketlerle uyumlu olması gerekir.
- **Model indirilemiyor:** İlk çalıştırmada internet bağlantısını kontrol edin. Uygulama modeli çalışma klasöründeki `hand_landmarker.task` dosyasında arar.
- **Tutam algılaması zor veya fazla hassas:** `PINCH_AC` ve `PINCH_BIRAK` değerlerini birlikte ayarlayın.
- **Çizgi titriyor:** Daha iyi ışıkta deneyin; yumuşatmayı artırmak için `TITREME_MIN` değerini azaltın. Daha fazla yumuşatma gecikmeyi artırabilir.
- **Klavye kısayolları çalışmıyor:** Önce **Havada Cizim** penceresine tıklayın ve tuşu yeniden deneyin. Uygulama tuşları OpenCV penceresinden okur; terminale yazılan tuşlar uygulamaya iletilmez.

## Kullanılan kütüphaneler

- [OpenCV](https://opencv.org/) — kamera görüntüsü, çizim ve pencere arayüzü
- [MediaPipe](https://ai.google.dev/edge/mediapipe) — el ve parmak noktalarının takibi
- [NumPy](https://numpy.org/) — görüntü dizileri ve matematiksel işlemler
