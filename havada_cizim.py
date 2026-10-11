import colorsys
import os
import time
import urllib.request
from collections import deque
from math import hypot, pi

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

# ======================= EL MODELI =======================
MODEL = "hand_landmarker.task"
URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
       "hand_landmarker/float16/1/hand_landmarker.task")
if not os.path.exists(MODEL):
    print("Model indiriliyor...")
    urllib.request.urlretrieve(URL, MODEL)

detector = vision.HandLandmarker.create_from_options(
    vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    )
)

# ======================= AYARLAR =======================
W, H = 1280, 720                 # pencere boyutu
# sag panelin baslangic x'i (cizim alani 0..PX)
PX = W - 280
IX, IW = PX + 20, 240            # panel ici: baslangic ve genislik

HUE = (IX, 78, IW, 40)           # gokkusagi cubugu (x, y, genislik, yukseklik)
SV = (IX, 134, IW, 170)          # ton / parlaklik karesi
BOYUT = (IX, 350, IW, 24)        # kalinlik cubugu
BTN_W, BTN_H = 112, 52
BUTONLAR = {"SILGI": (IX, 470), "GERI AL": (IX + 128, 470),
            "TEMIZLE": (IX, 534), "KAYDET": (IX + 128, 534),
            "SIMETRI": (IX, 598), "SEKIL": (IX + 128, 598)}

MIN_BOYUT, MAX_BOYUT = 2, 60
# tutam hassasiyeti (kucuk = daha siki tutam)
PINCH_AC, PINCH_BIRAK = 0.25, 0.38
# titreme filtresi (kucuk min = daha yumusak)
TITREME_MIN, TITREME_BETA = 1.2, 0.02

FONT = cv2.FONT_HERSHEY_SIMPLEX


# ======================= YARDIMCILAR =======================
class OneEuro:
    """Yavasken cok yumusatir, hizli hareket ederken gecikmez."""

    def __init__(self, min_cutoff=TITREME_MIN, beta=TITREME_BETA, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.reset()

    def reset(self):
        self.x_prev = None
        self.dx_prev = 0.0
        self.t_prev = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2 * pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, t):
        if self.x_prev is None:
            self.x_prev, self.t_prev = x, t
            return x
        dt = max(t - self.t_prev, 1e-3)
        dx = (x - self.x_prev) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        dx_hat = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev, self.t_prev = x_hat, dx_hat, t
        return x_hat


def sinirla(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def icinde(x, y, rect, pay=0):
    rx, ry, rw, rh = rect
    return rx - pay <= x <= rx + rw + pay and ry - pay <= y <= ry + rh + pay


def yazi(img, metin, konum, olcek=0.6, renk=(255, 255, 255), kal=1, kontur=True):
    if kontur:
        cv2.putText(img, metin, konum, FONT, olcek,
                    (0, 0, 0), kal + 2, cv2.LINE_AA)
    cv2.putText(img, metin, konum, FONT, olcek, renk, kal, cv2.LINE_AA)


def yuvarlak_dikdortgen(img, p1, p2, renk, r=12):
    (x1, y1), (x2, y2) = p1, p2
    cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), renk, -1)
    cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), renk, -1)
    for cx, cy in ((x1 + r, y1 + r), (x2 - r, y1 + r), (x1 + r, y2 - r), (x2 - r, y2 - r)):
        cv2.circle(img, (cx, cy), r, renk, -1, cv2.LINE_AA)


def hue_bar():
    hsv = np.zeros((1, HUE[2], 3), np.uint8)
    hsv[0, :, 0] = np.linspace(0, 179, HUE[2])
    hsv[0, :, 1:] = 255
    return np.repeat(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), HUE[3], axis=0)


def sv_kare(hue):
    sw, sh = SV[2], SV[3]
    s = np.linspace(0, 255, sw).astype(np.uint8)[None, :].repeat(sh, 0)
    v = np.linspace(255, 0, sh).astype(np.uint8)[:, None].repeat(sw, 1)
    h = np.full((sh, sw), int(hue * 179), np.uint8)
    return cv2.cvtColor(np.dstack([h, s, v]), cv2.COLOR_HSV2BGR)


def bgr_renk(hue, sat, val):
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return (int(b * 255), int(g * 255), int(r * 255))


def kaydet(canvas):
    var = canvas[:, :, 3:4] > 0
    cikti = np.where(var, canvas[:, :, :3], 255).astype(
        np.uint8)   # beyaz zemin
    dosya = f"cizim_{int(time.time())}.png"
    cv2.imwrite(dosya, cikti)
    return dosya


# ---------------------- SEKIL TANIMA ----------------------
def sekil_tani(noktalar):
    """Cizilen yolu tanir. (ad, nokta_listesi, kapali_mi) ya da None dondurur.
    Tanimazsa None doner ve cizim oldugu gibi kalir (kalp, yildiz, serbest cizim)."""
    if len(noktalar) < 10:
        return None
    p = np.array(noktalar, np.float32)
    # hafif yumusatma (5'li ortalama)
    pad = np.pad(p, ((2, 2), (0, 0)), mode="edge")
    p = np.stack([np.convolve(pad[:, i], np.ones(5) / 5, mode="valid") for i in range(2)],
                 axis=1).astype(np.float32)
    _, _, w, h = cv2.boundingRect(p.reshape(-1, 1, 2))
    diag = hypot(w, h)
    if diag < 50:                      # cok kucuk, nokta/karalama
        return None
    ilk, son = p[0], p[-1]
    bosluk = hypot(float(ilk[0] - son[0]), float(ilk[1] - son[1]))

    # --- ACIK cizgi: duz cizgi mi? ---
    if bosluk > 0.3 * diag:
        dx, dy = float(son[0] - ilk[0]), float(son[1] - ilk[1])
        uzun = hypot(dx, dy)
        if uzun < 40:
            return None
        sapma = np.abs(dx * (p[:, 1] - ilk[1]) -
                       dy * (p[:, 0] - ilk[0])) / uzun
        if sapma.max() < 0.07 * uzun:
            a = [float(ilk[0]), float(ilk[1])]
            b = [float(son[0]), float(son[1])]
            if abs(dy) < 0.1 * abs(dx):        # yatay'a yapistir
                b[1] = a[1]
            elif abs(dx) < 0.1 * abs(dy):      # dikey'e yapistir
                b[0] = a[0]
            return "CIZGI", [a, b], False
        return None

    # --- KAPALI sekil ---
    kontur = p.reshape(-1, 1, 2)
    alan = cv2.contourArea(kontur)
    hull = cv2.convexHull(kontur)
    h_alan = cv2.contourArea(hull)
    h_cevre = cv2.arcLength(hull, True)
    if h_alan < 1 or h_cevre < 1:
        return None
    # girintili sekiller (kalp, yildiz...) -> oldugu gibi birak:
    # cizgi uzerindeki en derin nokta, zarf (hull) kenarindan ne kadar iceride?
    derinlik = max(cv2.pointPolygonTest(hull, (float(a), float(b)), True)
                   for a, b in p) / (h_alan ** 0.5)
    if derinlik > 0.12:
        return None

    # daire = 1.0, kare = 0.78
    yuvarlak = 4 * pi * h_alan / (h_cevre ** 2)
    if yuvarlak > 0.86:
        (cx, cy), (ea, eb), aci = cv2.fitEllipse(kontur)
        if min(ea, eb) / max(ea, eb) > 0.85:           # neredeyse daire
            ea = eb = (ea + eb) / 2
            ad = "DAIRE"
        else:
            ad = "ELIPS"
        pts = cv2.ellipse2Poly((int(cx), int(cy)), (int(ea / 2), int(eb / 2)),
                               int(aci), 0, 360, 6)
        return ad, pts.tolist(), True

    approx = cv2.approxPolyDP(hull, 0.045 * h_cevre, True).reshape(-1, 2)
    n = len(approx)
    if n == 3:
        return "UCGEN", approx.tolist(), True
    if n == 4:
        bx, by, bw, bh = cv2.boundingRect(approx.reshape(-1, 1, 2))
        if cv2.contourArea(approx.reshape(-1, 1, 2)) > 0.85 * bw * bh:
            return "DIKDORTGEN", [[bx, by], [bx + bw, by], [bx + bw, by + bh], [bx, by + bh]], True
        return "DORTGEN", approx.tolist(), True
    return None


def sekil_ciz(canvas, pts, kapali, renk, kal):
    pts = [(int(round(a)), int(round(b))) for a, b in pts]
    n = len(pts)
    for i in range(n if kapali else n - 1):
        cv2.line(canvas, pts[i], pts[(i + 1) % n], renk, kal)
    for q in pts:
        cv2.circle(canvas, q, kal // 2, renk, -1)


def parca_ciz(canvas, a, b, renk, kal, ayna):
    """a -> b arasini cizer; ayna aciksa dikey eksene gore yansimasini da cizer."""
    if a:
        cv2.line(canvas, a, b, renk, kal)
    cv2.circle(canvas, b, kal // 2, renk, -1)
    if ayna:
        b2 = (PX - b[0], b[1])
        if a:
            cv2.line(canvas, (PX - a[0], a[1]), b2, renk, kal)
        cv2.circle(canvas, b2, kal // 2, renk, -1)


# ---------------------- ARAYUZ ----------------------
def panel_ciz(kare, imlec, hue, sat, val, boyut, bgr, silgi, acik, hue_img, sv_img):
    # buzlu cam efekti
    roi = cv2.GaussianBlur(kare[:, PX:], (41, 41), 0)
    koyu = np.full_like(roi, (40, 30, 30))
    kare[:, PX:] = cv2.addWeighted(roi, 0.25, koyu, 0.75, 0)
    cv2.line(kare, (PX, 0), (PX, H), (120, 100, 100), 1)

    yazi(kare, "HAVADA CIZIM", (IX, 42), 0.8, (255, 255, 255), 2, kontur=False)

    # --- gokkusagi cubugu ---
    hx, hy, hw, hh = HUE
    yazi(kare, "RENK", (IX, hy - 10), 0.5, (200, 200, 200), kontur=False)
    kare[hy:hy + hh, hx:hx + hw] = hue_img
    cv2.rectangle(kare, (hx, hy), (hx + hw, hy + hh), (255, 255, 255), 1)
    mx = hx + int(hue * (hw - 1))
    cv2.rectangle(kare, (mx - 4, hy - 5),
                  (mx + 4, hy + hh + 5), (255, 255, 255), 2)

    # --- ton / parlaklik karesi (renk karisimi) ---
    sx, sy, sw, sh = SV
    kare[sy:sy + sh, sx:sx + sw] = sv_img
    cv2.rectangle(kare, (sx, sy), (sx + sw, sy + sh), (255, 255, 255), 1)
    cx, cy = sx + int(sat * (sw - 1)), sy + int((1 - val) * (sh - 1))
    cv2.circle(kare, (cx, cy), 9, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.circle(kare, (cx, cy), 9, (255, 255, 255), 2, cv2.LINE_AA)

    # --- kalinlik cubugu ---
    bx, by, bw, bh = BOYUT
    cy = by + bh // 2
    yazi(kare, f"KALINLIK: {boyut}", (bx, by - 12),
         0.55, (200, 200, 200), kontur=False)
    cv2.line(kare, (bx, cy), (bx + bw, cy), (90, 80, 80), 8, cv2.LINE_AA)
    kx = bx + int((boyut - MIN_BOYUT) / (MAX_BOYUT - MIN_BOYUT) * bw)
    cv2.line(kare, (bx, cy), (kx, cy), (255, 255, 255)
             if silgi else bgr, 8, cv2.LINE_AA)
    cv2.circle(kare, (kx, cy), 14, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(kare, (kx, cy), 8, (255, 255, 255)
               if silgi else bgr, -1, cv2.LINE_AA)

    # --- onizleme ---
    pc = (PX + 140, 418)
    r = min((max(boyut * 2, 24) if silgi else boyut) // 2, 34)
    cv2.circle(kare, pc, 36, (90, 80, 80), 1, cv2.LINE_AA)
    if silgi:
        cv2.circle(kare, pc, r, (255, 255, 255), 2, cv2.LINE_AA)
    else:
        cv2.circle(kare, pc, r, bgr, -1, cv2.LINE_AA)

    # --- butonlar ---
    for ad, (bx, by) in BUTONLAR.items():
        uzerinde = bool(
            imlec) and bx <= imlec[0] <= bx + BTN_W and by <= imlec[1] <= by + BTN_H
        if acik.get(ad, False):
            renk = (200, 110, 255)
        elif uzerinde:
            renk = (120, 100, 100)
        else:
            renk = (80, 66, 66)
        yuvarlak_dikdortgen(kare, (bx, by), (bx + BTN_W, by + BTN_H), renk, 12)
        (tw, th), _ = cv2.getTextSize(ad, FONT, 0.6, 2)
        cv2.putText(kare, ad, (bx + (BTN_W - tw) // 2, by + (BTN_H + th) // 2),
                    FONT, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

    yazi(kare, "Bas + isaret parmagini", (IX, 682),
         0.5, (190, 190, 190), kontur=False)
    yazi(kare, "birlestir = CIZ / SEC", (IX, 704),
         0.5, (190, 190, 190), kontur=False)


# ======================= DURUM =======================
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

canvas = np.zeros((H, W, 4), np.uint8)      # BGR + alfa (0 = seffaf)
gecmis = deque(maxlen=20)                   # geri al icin kayitlar
hue, sat, val = 0.0, 1.0, 1.0
boyut = 10
silgi = False
simetri = False                             # ayna modu
sekil_modu = False                          # sekil tanima
hue_img = hue_bar()
sv_img, sv_hue = sv_kare(hue), hue
bgr = bgr_renk(hue, sat, val)

fx, fy = OneEuro(), OneEuro()
tutam = eski_tutam = False
aktif = None            # "cizim", "hue", "sv", "boyut" ya da None
onceki = None
cizgi = []              # o an cizilen yolun noktalari (sekil tanima icin)
kayip = 0
son_imlec = None
mesaj, mesaj_bitis = "", 0.0
t0 = time.time()
son_ts = -1

# ======================= ANA DONGU =======================
while True:
    ok, kare = cap.read()
    if not ok:
        print("Kamera bulunamadi")
        break

    kare = cv2.flip(kare, 1)
    kare = cv2.resize(kare, (W, H))
    simdi = time.time()

    rgb = cv2.cvtColor(kare, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    ts = max(int((simdi - t0) * 1000), son_ts + 1)
    son_ts = ts
    sonuc = detector.detect_for_video(mp_img, ts)

    # --- el + tutam algilama ---
    imlec = None
    parmaklar = None
    if sonuc.hand_landmarks:
        kayip = 0
        lm = sonuc.hand_landmarks[0]
        bas = (lm[4].x * W, lm[4].y * H)       # basparmak ucu
        isr = (lm[8].x * W, lm[8].y * H)       # isaret parmagi ucu
        el_boyu = hypot((lm[0].x - lm[9].x) * W, (lm[0].y - lm[9].y) * H)
        oran = hypot(bas[0] - isr[0], bas[1] - isr[1]) / max(el_boyu, 1)

        if not tutam and oran < PINCH_AC:
            tutam = True
        elif tutam and oran > PINCH_BIRAK:
            tutam = False

        # imlec: iki parmak ucunun ortasi (tutarken kaymaz) + titreme filtresi
        x = fx((bas[0] + isr[0]) / 2, simdi)
        y = fy((bas[1] + isr[1]) / 2, simdi)
        imlec = son_imlec = (int(x), int(y))
        parmaklar = (bas, isr)
    else:
        kayip += 1
        if kayip <= 5:                         # kisa kopmalarda cizgi bolunmesin
            imlec = son_imlec
        else:
            tutam = False
            fx.reset()
            fy.reset()
            son_imlec = None

    basladi = tutam and not eski_tutam
    bitti = eski_tutam and not tutam
    eski_tutam = tutam

    # --- tutam bitti: sekil tanima ---
    if bitti and aktif == "cizim" and sekil_modu and not silgi:
        bulunan = sekil_tani(cizgi)
        if bulunan and gecmis:
            ad_s, pts_s, kapali_s = bulunan
            canvas[:] = gecmis[-1]                        # elle cizileni sil
            renk_s = (*bgr, 255)
            sekil_ciz(canvas, pts_s, kapali_s, renk_s, boyut)
            if simetri:
                sekil_ciz(canvas, [(PX - a, b)
                          for a, b in pts_s], kapali_s, renk_s, boyut)
            mesaj = f"{ad_s} tanindi"
            mesaj_bitis = simdi + 1.5
    if bitti:
        cizgi = []

    if not tutam:
        aktif = None
        onceki = None

    # --- tutam baslangici: neye basildi? ---
    if imlec:
        x, y = imlec
        if basladi:
            if x >= PX:                                     # panel
                aktif = None
                if icinde(x, y, HUE, 12):
                    aktif = "hue"
                elif icinde(x, y, SV, 6):
                    aktif = "sv"
                elif icinde(x, y, BOYUT, 20):
                    aktif = "boyut"
                else:
                    for ad, (bx, by) in BUTONLAR.items():
                        if bx <= x <= bx + BTN_W and by <= y <= by + BTN_H:
                            if ad == "SILGI":
                                silgi = not silgi
                            elif ad == "GERI AL":
                                if gecmis:
                                    canvas[:] = gecmis.pop()
                            elif ad == "TEMIZLE":
                                gecmis.append(canvas.copy())
                                canvas[:] = 0
                            elif ad == "KAYDET":
                                mesaj = f"Kaydedildi: {kaydet(canvas)}"
                                mesaj_bitis = simdi + 2.5
                            elif ad == "SIMETRI":
                                simetri = not simetri
                            elif ad == "SEKIL":
                                sekil_modu = not sekil_modu
            else:                                           # tuval
                aktif = "cizim"
                gecmis.append(canvas.copy())
                onceki = None
                cizgi = []

        # --- tutarken: cubuklari surukle ---
        if tutam:
            if aktif == "hue":
                hue = sinirla((x - IX) / IW)
                silgi = False
            elif aktif == "sv":
                sat = sinirla((x - IX) / IW)
                val = 1 - sinirla((y - SV[1]) / SV[3])
                silgi = False
            elif aktif == "boyut":
                boyut = int(MIN_BOYUT + sinirla((x - IX) / IW)
                            * (MAX_BOYUT - MIN_BOYUT))

    bgr = bgr_renk(hue, sat, val)
    if hue != sv_hue:
        sv_img, sv_hue = sv_kare(hue), hue

    # --- cizim ---
    if imlec and tutam and aktif == "cizim":
        x, y = imlec
        if x < PX:
            renk = (0, 0, 0, 0) if silgi else (*bgr, 255)
            kal = max(boyut * 2, 24) if silgi else boyut
            parca_ciz(canvas, onceki, (x, y), renk, kal, simetri)
            onceki = (x, y)
            cizgi.append((x, y))
        else:
            onceki = None

    # --- tuvali kameranin ustune koy ---
    maske = canvas[:, :, 3] > 0
    kare[maske] = canvas[:, :, :3][maske]

    # --- simetri ekseni ---
    if simetri:
        for yy in range(0, H, 24):
            cv2.line(kare, (PX // 2, yy),
                     (PX // 2, yy + 12), (255, 255, 255), 1)

    # --- arayuz ---
    acik = {"SILGI": silgi, "SIMETRI": simetri, "SEKIL": sekil_modu}
    panel_ciz(kare, imlec, hue, sat, val, boyut,
              bgr, silgi, acik, hue_img, sv_img)

    # --- imlec ---
    if imlec:
        x, y = imlec
        if parmaklar:
            p1 = (int(parmaklar[0][0]), int(parmaklar[0][1]))
            p2 = (int(parmaklar[1][0]), int(parmaklar[1][1]))
            cv2.line(kare, p1, p2, (255, 255, 0), 1, cv2.LINE_AA)
            cv2.circle(kare, p1, 6, (255, 255, 0), -1, cv2.LINE_AA)
            cv2.circle(kare, p2, 6, (255, 255, 0), -1, cv2.LINE_AA)
        if x >= PX:
            r = 12
        else:
            r = max((max(boyut * 2, 24) if silgi else boyut) // 2, 6)
            if simetri:                                      # yansima imleci
                cv2.circle(kare, (PX - x, y), r,
                           (255, 255, 255), 1, cv2.LINE_AA)
        if tutam:
            cv2.circle(kare, imlec, r, (255, 255, 255)
                       if silgi else bgr, -1, cv2.LINE_AA)
            cv2.circle(kare, imlec, r, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            cv2.circle(kare, imlec, r, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.circle(kare, imlec, 3, bgr, -1, cv2.LINE_AA)

    # --- durum yazisi ---
    if imlec is None:
        yazi(kare, "EL GORUNMUYOR", (20, 40), 0.7, (180, 180, 180), 2)
    elif tutam:
        yazi(kare, "CIZIYOR" if aktif == "cizim" else "AYAR",
             (20, 40), 0.7, (0, 255, 120), 2)
    else:
        yazi(kare, "HAZIR - cizmek icin basparmak + isaret parmagini birlestir",
             (20, 40), 0.7, (255, 255, 255), 2)
    modlar = [m for m, a in (("SIMETRI", simetri),
                             ("SEKIL TANIMA", sekil_modu)) if a]
    if modlar:
        yazi(kare, "Mod: " + " + ".join(modlar),
             (20, 72), 0.6, (200, 110, 255), 2)
    if simdi < mesaj_bitis:
        yazi(kare, mesaj, (20, H - 25), 0.7, (0, 255, 0), 2)

    cv2.imshow("Havada Cizim", kare)
    tus = cv2.waitKey(1) & 0xFF
    if tus == ord("q"):
        break
    elif tus == ord("c"):
        gecmis.append(canvas.copy())
        canvas[:] = 0
    elif tus == ord("z") and gecmis:
        canvas[:] = gecmis.pop()
    elif tus == ord("m"):
        simetri = not simetri
    elif tus == ord("t"):
        sekil_modu = not sekil_modu
    elif tus == ord("s"):
        mesaj = f"Kaydedildi: {kaydet(canvas)}"
        mesaj_bitis = time.time() + 2.5

cap.release()
cv2.destroyAllWindows()
detector.close()
