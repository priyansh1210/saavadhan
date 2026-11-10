"""Sentences for the instant scam check, written the way people actually speak and type them.

Labels (what the live risk must be, from the rules alone):
  scam   -> 70 or more (the alarm fires)
  warn   -> 35 or more (at least "careful")
  nowarn -> under 70 (harmless but sensitive words; "careful" is acceptable, an alarm is not)
  safe   -> under 35
"""

SCAM = [
    # someone in the family is "arrested" or in trouble, send money
    "me ek police officer hu aapka baccha humari arrest me he , usse chudane ke liye 500000 rupay bhejiye",
    "Aapka beta police custody mein hai, usko chhudana hai toh 50 hazaar abhi bhejo",
    "Main thane se bol raha hoon, aapki beti ko drugs ke saath pakda hai, case band karne ke liye 2 lakh bhejiye",
    "Your son has been arrested, pay 2 lakh now to release him",
    "आपका बेटा हमारी हिरासत में है, उसे छुड़ाने के लिए पैसे भेजिए",
    "Papa main musibat mein hoon, kisi ko mat batana, jaldi 20000 bhej do is number pe",
    "aapke bete ka accident ho gaya hai hospital me bharti hai turant 30000 rupaye bhejiye",
    "inspector bol raha hu aapka ladka jail jayega, zamanat ke liye 1 lakh transfer karo",
    # digital arrest
    "Aap digital arrest mein hain, video call band mat kijiye aur kisi ko mat bataiye",
    "You are under digital arrest, do not disconnect the call and do not tell anyone",
    "Customs se bol rahe hain, aapke parcel mein drugs mile hain, aapke naam pe FIR hogi, verification fee bhejiye",
    "CBI se bol raha hoon, aapke naam pe money laundering ka case hai, ghar walon ko mat batana",
    "आप डिजिटल अरेस्ट में हैं, यह बात किसी को भी मत बताइए",
    # bank, KYC, OTP, card
    "Aapka KYC expire ho gaya hai, account block ho jayega, OTP bataiye",
    "Sir bank se bol raha hoon, aapka card band ho jayega, card ke peeche ka CVV bata dijiye",
    "Your SBI account will be blocked today, share the OTP to update KYC",
    "UPI pin daalo, paise aapke account mein aa jayenge",
    "आपका खाता बंद हो जाएगा, ओटीपी बताइए",
    "main Paytm se bol raha hu cashback ke liye apna upi pin daaliye",
    "aapka atm card block ho gaya hai pin number bata do abhi chalu kar dunga",
    # remote access
    "AnyDesk app download kar lijiye, main aapka refund turant process kar deta hoon, OTP bhi bata dena",
    "Ye APK download karo, bijli bill update ho jayega warna aaj raat connection kat jayega",
    # prize, job, refund
    "Badhai ho aapne KBC lottery mein 25 lakh jeete hain, processing fee 15000 bhejiye",
    "Congratulations, you won a prize. Pay the registration charge now to claim it",
    "Work from home job hai, joining ke liye 2000 security deposit turant bhejiye",
    # utility
    "Aaj raat 9 baje aapki bijli kaat di jayegi, turant is number pe bill pay karo",
    "बिजली का कनेक्शन आज रात कट जाएगा, अभी के अभी पैसे भेजिए",
    # pressure plus secrecy
    "Phone mat kaatna, abhi ke abhi paise transfer karo, kisi ko mat bolna",
]

WARN = [
    "CBI officer bol raha hoon, aapke Aadhaar se money laundering hui hai",
    "आपके नाम पर गिरफ्तारी वारंट जारी हुआ है",
    "Narcotics department se bol rahe hain, aapka FedEx parcel pakda gaya hai",
    "OTP share kar dijiye, verification ke liye",
    "Screen share on kijiye, main aapki help karta hoon",
    "Ek link bheja hai, us par click karke apna detail bhariye",
    "Please install TeamViewer so I can fix your bank app",
    "Aapka refund atka hua hai, 10 rupaye ka payment karo phir refund aa jayega",
    "TRAI se bol rahe hain, aapka SIM 2 ghante mein band ho jayega",
    "Aapke number se illegal activity hui hai, officer se baat kijiye",
    "Paisa double karne wali scheme hai, 10000 lagao 1 lakh pao, guaranteed return",
    "Ye baat ghar walon ko mat batana",
    "sir aapka parcel customs me ruka hai clearance charge dena padega",
]

NOWARN = [
    "Your HDFC credit card bill of 5000 is due tomorrow, please pay through the app",
    "Swiggy order aa raha hai, OTP ready rakhiye delivery ke time",
    "OTP aaya hai, main abhi login kar raha hoon",
    "Main tumhe screen share karke presentation dikhata hoon",
    "Bank ki branch mein KYC update karwane jana hai kal",
    "Police verification ke liye passport office jana hai",
    "Mera Aadhaar card kho gaya, naya banwana hai",
]

SAFE = [
    "Beta, khana kha liya? Papa kaise hain?",
    "Haan main bilkul fine hoon, tum batao",
    "Main turant aata hoon, gate pe ruko",
    "Mera pin code 110001 hai, parcel yahin bhej dena",
    "Amazon delivery hai, aapka parcel gate pe rakh doon?",
    "Maine tumhe 500 rupaye bhej diye hain, check kar lo",
    "Kal school ki fees jama karni hai, 5000 rupaye leke jana",
    "Doctor ne bola hai report kal aayegi",
    "Police station mein meri complaint ka kya hua?",
    "Mummy main hostel pahunch gaya, kal call karta hoon",
    "Bhaiya meeting mein hoon, baad mein baat karte hain",
    "Electricity bill aa gaya hai, main online bhar dunga",
    "Mera beta kal exam dene ja raha hai",
    "Aapka beta school mein hai, chhutti 3 baje hogi",
    "Court ki tareekh kal hai, vakil se baat ho gayi",
    "Hello sir, main Zomato se bol raha hoon, aapka order 10 minute mein pahunchega",
    "Maa, maine fees ke liye 2000 bhej diye",
    "Aapke account mein salary credit ho gayi hai",
    "Hi, this is your dentist's office confirming your appointment tomorrow at 10",
    "I will transfer the rent tomorrow morning",
    "बेटा, खाना खा लिया?",
    "मैं दस मिनट में पहुँच रहा हूँ",
    "Bijli chali gayi thi, inverter chal raha hai",
    "Uncle ji ka accident hua tha par ab woh theek hain, ghar aa gaye",
    "Arre yaar traffic police ne challan kaat diya aaj",
    "Paise ki tension mat lo, main sambhal lunga",
    "Kal bank jaake passbook update karwa lena",
    "Office mein naya inspector aaya hai audit ke liye",
]

CASES = [(t, "scam") for t in SCAM] + [(t, "warn") for t in WARN] + \
        [(t, "nowarn") for t in NOWARN] + [(t, "safe") for t in SAFE]


def passes(label: str, live: int) -> bool:
    return {"scam": live >= 70, "warn": live >= 35, "nowarn": live < 70, "safe": live < 35}[label]
