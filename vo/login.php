<?php
$results = [];

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['login'])) {
    $numbers  = explode(',', $_POST['number']);
    $password = $_POST['password'] ?? '';

    foreach ($numbers as $number) {
        $number = trim($number);
        $entry  = ['number'=>$number,'success'=>false,'message'=>'','promos'=>[]];

        if (!$number || !$password) {
            $entry['message'] = 'الرجاء إدخال رقم الموبايل وكلمة المرور';
        } else {
            $url      = "https://mobile.vodafone.com.eg/auth/realms/vf-realm/protocol/openid-connect/token";
            $postData = http_build_query(['grant_type'=>'password','username'=>$number,'password'=>$password,'client_secret'=>'95fd95fb-7489-4958-8ae6-d31a525cd20a','client_id'=>'ana-vodafone-app']);
            $ch = curl_init($url);
            curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_POST=>true,CURLOPT_POSTFIELDS=>$postData,CURLOPT_HTTPHEADER=>["Content-Type: application/x-www-form-urlencoded","Accept: application/json","User-Agent: okhttp/4.11.0"]]);
            $response = curl_exec($ch); curl_close($ch);
            $data = json_decode($response, true);

            if (!isset($data['access_token'])) {
                $entry['message'] = "فشل تسجيل الدخول: تحقق من الرقم أو كلمة المرور";
            } else {
                $entry['success'] = true;
                $promoUrl = "https://web.vodafone.com.eg/services/dxl/ramadanpromo/promotion?@type=RamadanHub&channel=website&msisdn=".urlencode($number);
                $ch = curl_init($promoUrl);
                curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_HTTPHEADER=>["Authorization: Bearer ".$data['access_token'],"User-Agent: Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36","Accept: application/json","clientId: WebsiteConsumer","api-host: PromotionHost","channel: WEB","Accept-Language: ar","msisdn: ".$number,"Content-Type: application/json","Referer: https://web.vodafone.com.eg/ar/ramadan"]]);
                $promoResponse = curl_exec($ch); curl_close($ch);
                $decoded = json_decode($promoResponse, true);

                $promoCards = [];
                if (is_array($decoded)) {
                    foreach ($decoded as $item) {
                        if (!is_array($item) || !isset($item['pattern'])) continue;
                        foreach ($item['pattern'] as $pattern) {
                            if (!isset($pattern['action'])) continue;
                            foreach ($pattern['action'] as $action) {
                                $chars = [];
                                foreach ($action['characteristics'] ?? [] as $c) {
                                    $chars[$c['name']] = (string)$c['value'];
                                }
                                if (!empty($chars)) {
                                    $serial = (string)($chars['CARD_SERIAL'] ?? '');
                                    if (strlen($serial) !== 13) continue;
                                    $promoCards[] = [
                                        'amount'      => $chars['amount'] ?? '0',
                                        'gift'        => $chars['GIFT_UNITS'] ?? '0',
                                        'remaining'   => $chars['REMAINING_DEDICATIONS'] ?? '0',
                                        'card_serial' => $serial
                                    ];
                                }
                            }
                        }
                    }
                }
                usort($promoCards, fn($a,$b) => (int)$b['amount'] - (int)$a['amount']);
                $entry['promos'] = $promoCards;
            }
        }
        $results[] = $entry;
    }
}
?>
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"/>
<title>TALASHNY - عروض فودافون</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css"/>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap" rel="stylesheet"/>
<style>
:root {
    --red:#e60000; --red-glow:rgba(230,0,0,0.45); --red-soft:rgba(230,0,0,0.12);
    --text-dark:#111; --text-muted:#888; --bg:#f7f7f9;
    --surface:rgba(255,255,255,0.72); --border:rgba(0,0,0,0.08);
    --shadow-sm:0 2px 12px rgba(0,0,0,0.08);
    --radius-sm:10px; --radius-md:18px; --radius-lg:28px;
    --ease-spring:cubic-bezier(0.34,1.56,0.64,1);
    --ease-out:cubic-bezier(0.25,0.46,0.45,0.94);
    --ease-smooth:cubic-bezier(0.4,0,0.2,1);
}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box;-webkit-user-select:none!important;user-select:none!important}
html,body{height:100%;overflow-x:hidden;touch-action:manipulation}
body{font-family:'Cairo',sans-serif;background:var(--bg);color:var(--text-dark);min-height:100vh;padding-top:175px;padding-bottom:110px;
background-image:radial-gradient(ellipse at 20% 50%,rgba(230,0,0,0.04) 0%,transparent 60%),radial-gradient(ellipse at 80% 20%,rgba(230,0,0,0.03) 0%,transparent 50%),url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.025'/%3E%3C/svg%3E");}

/* BANNER */
.banner{position:fixed;top:0;left:0;right:0;width:100%;height:95px;background:#000;padding:20px 0;font-size:2.8rem;font-weight:900;letter-spacing:6px;text-transform:uppercase;box-shadow:0 6px 40px rgba(0,0,0,0.8),0 0 0 1px rgba(255,255,255,0.05) inset;z-index:1000;border-bottom-left-radius:60% 40%;border-bottom-right-radius:60% 40%;overflow:hidden;display:flex;justify-content:center;align-items:center;gap:5px}
.banner::after{content:'';position:absolute;bottom:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.15),transparent)}
.banner span{display:inline-block;color:transparent;background:linear-gradient(90deg,#c0c0c0 0%,#fff 20%,#e0e0e0 40%,#fff 60%,#b0b0b0 80%,#c0c0c0 100%);background-size:400% 100%;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:chrome-shine 4s linear infinite;animation-delay:calc(var(--i)*0.18s)}
.banner span:nth-child(1){--i:0}.banner span:nth-child(2){--i:1}.banner span:nth-child(3){--i:2}.banner span:nth-child(4){--i:3}.banner span:nth-child(5){--i:4}.banner span:nth-child(6){--i:5}.banner span:nth-child(7){--i:6}.banner span:nth-child(8){--i:7}
@keyframes chrome-shine{0%{background-position:400% center}100%{background-position:-400% center}}

.small-logo-under-banner{position:fixed;top:100px;left:51%;transform:translateX(-50%);z-index:999;margin-top:8px}
.small-logo-under-banner img{width:38px;height:auto;display:block;filter:drop-shadow(0 1px 4px rgba(0,0,0,0.6))}

.ramadan-decoration{position:fixed;top:85px;left:0;right:0;height:170px;pointer-events:none;z-index:999;display:flex;justify-content:space-between;align-items:flex-start;padding:0 2px}
.garland-left,.garland-right{width:auto;max-width:45%;height:auto;max-height:100%;object-fit:contain;filter:drop-shadow(0 4px 12px rgba(0,0,0,0.5))}
.garland-left{animation:swing-left 24s infinite ease-in-out;transform-origin:top left}
.garland-right{animation:swing-right 26s infinite ease-in-out;transform-origin:top right}
@keyframes swing-left{0%,100%{transform:rotate(0deg)}50%{transform:rotate(-1.5deg)}}
@keyframes swing-right{0%,100%{transform:rotate(0deg)}50%{transform:rotate(1.5deg)}}

.container{max-width:480px;margin:0 auto;padding:0 18px}
.login-content{margin-top:15px}

.logo{text-align:center;margin:25px 0}
.custom-logo{width:135px;height:135px;object-fit:contain;border-radius:50%;box-shadow:0 8px 40px rgba(230,0,0,0.35),0 0 0 3px rgba(230,0,0,0.1),0 0 0 8px rgba(230,0,0,0.04);margin:15px auto;display:block;animation:logo-breathe 4s ease-in-out infinite}
@keyframes logo-breathe{0%,100%{box-shadow:0 8px 40px rgba(230,0,0,0.35),0 0 0 3px rgba(230,0,0,0.1),0 0 0 8px rgba(230,0,0,0.04)}50%{box-shadow:0 12px 55px rgba(230,0,0,0.5),0 0 0 3px rgba(230,0,0,0.2),0 0 0 14px rgba(230,0,0,0.07)}}
.title{font-size:1.95rem;font-weight:900;text-align:center;margin-bottom:10px}
.subtitle{font-size:1rem;color:var(--text-muted);text-align:center;margin-bottom:35px}

.input-wrapper{position:relative;margin-bottom:20px}
.input-wrapper input{width:100%;padding:16px 18px 16px 52px;border:1.5px solid var(--border);border-radius:var(--radius-md);font-size:1.05rem;font-family:'Cairo',sans-serif;background:var(--surface);backdrop-filter:blur(20px) saturate(150%);-webkit-backdrop-filter:blur(20px) saturate(150%);color:var(--text-dark);outline:none;transition:border-color .3s var(--ease-smooth),box-shadow .3s var(--ease-smooth),background .3s var(--ease-smooth);box-shadow:var(--shadow-sm)}
.input-wrapper input::placeholder{color:var(--text-muted)}
.input-wrapper input:focus{border-color:var(--red);background:rgba(255,255,255,0.92);box-shadow:0 0 0 4px var(--red-soft),var(--shadow-sm)}
.input-icon{position:absolute;left:18px;top:50%;transform:translateY(-50%);color:var(--text-muted);font-size:1.25rem;pointer-events:none;transition:color .3s}
.input-wrapper:has(input:focus) .input-icon{color:var(--red)}

.btn-login{width:100%;padding:16px;background:#111;color:white;border:none;border-radius:var(--radius-md);font-size:1.2rem;font-weight:700;font-family:'Cairo',sans-serif;cursor:pointer;overflow:hidden;position:relative;transition:transform .3s var(--ease-spring),box-shadow .3s var(--ease-smooth);box-shadow:0 6px 24px rgba(0,0,0,0.3);letter-spacing:0.5px}
.btn-login::before{content:'';position:absolute;top:0;left:-100%;width:60%;height:100%;background:linear-gradient(120deg,transparent,rgba(255,255,255,0.15),transparent);transition:left .6s var(--ease-smooth)}
.btn-login:hover::before{left:140%}
.btn-login:hover{transform:translateY(-3px);box-shadow:0 12px 35px rgba(0,0,0,0.35)}
.btn-login:active{transform:translateY(0)}

.results-wrapper{display:block}

/* TIMER */
.timer-container{display:flex;flex-direction:column;align-items:center;margin:18px 0 30px;gap:10px}
.flip-scene{width:88px;height:88px;perspective:500px;position:relative}
.flip-face{width:100%;height:100%;background:linear-gradient(160deg,#1c1c1c 0%,#0d0d0d 100%);border-radius:22px;border:1px solid rgba(255,255,255,0.07);display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.7),0 0 0 1px rgba(230,0,0,0.18),inset 0 1px 0 rgba(255,255,255,0.07),inset 0 -1px 0 rgba(0,0,0,0.4)}
.flip-face::before{content:'';position:absolute;top:50%;left:0;right:0;height:1.5px;background:linear-gradient(90deg,transparent 0%,rgba(0,0,0,0.9) 20%,rgba(0,0,0,0.9) 80%,transparent 100%);z-index:5}
.flip-face::after{content:'';position:absolute;top:0;left:0;right:0;bottom:50%;background:linear-gradient(180deg,rgba(255,255,255,0.04) 0%,transparent 100%);border-radius:22px 22px 0 0;pointer-events:none}
.flip-tag{position:absolute;bottom:0;left:0;background:linear-gradient(135deg,#e60000,#c00000);font-size:0.48rem;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:white;padding:4px 10px 4px 6px;border-bottom-left-radius:20px;border-top-right-radius:10px;z-index:6}
.flip-number{font-size:3.6rem;font-weight:900;color:white;font-family:'Cairo',sans-serif;text-shadow:0 0 30px rgba(230,0,0,0.9),0 0 60px rgba(230,0,0,0.4),0 2px 4px rgba(0,0,0,0.8);position:relative;z-index:3;line-height:1}
.flip-corner-dot{position:absolute;top:10px;right:10px;width:7px;height:7px;border-radius:50%;background:#e60000;box-shadow:0 0 8px rgba(230,0,0,0.9),0 0 16px rgba(230,0,0,0.5);animation:dot-blink 1s ease-in-out infinite;z-index:6}
@keyframes dot-blink{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.3;transform:scale(0.7)}}
.flip-animate{animation:flip3d 0.52s cubic-bezier(0.455,0.03,0.515,0.955)}
@keyframes flip3d{0%{transform:rotateX(0deg);opacity:1}40%{transform:rotateX(-92deg);opacity:0.1}60%{transform:rotateX(92deg);opacity:0.1}100%{transform:rotateX(0deg);opacity:1}}
.flip-label-row{display:flex;align-items:center;gap:8px}
.flip-label-line{width:22px;height:1.5px;background:linear-gradient(90deg,transparent,rgba(230,0,0,0.5));border-radius:1px}
.flip-label-line.right{background:linear-gradient(90deg,rgba(230,0,0,0.5),transparent)}
.flip-label-text{font-size:0.7rem;font-weight:700;color:#e60000;letter-spacing:2.5px;text-transform:uppercase}

/* PROMO CARD */
.promo-card{background-image:url('https://tlashane.serv00.net/vo/sa-mobile.jpg');background-size:cover;background-position:center;position:relative;border-radius:var(--radius-md);overflow:hidden;margin-bottom:14px;box-shadow:0 6px 24px rgba(0,0,0,0.3);animation:cardIn 0.55s var(--ease-spring) both;animation-delay:calc(var(--index,0) * 0.13s)}
@keyframes cardIn{from{opacity:0;transform:translateY(28px) scale(0.96)}to{opacity:1;transform:none}}
.promo-card:hover{box-shadow:0 12px 36px rgba(0,0,0,0.4),0 0 0 1.5px rgba(230,0,0,0.35);transform:translateY(-3px);transition:transform .25s var(--ease-spring),box-shadow .25s}
.card-overlay{position:absolute;inset:0;background:linear-gradient(150deg,rgba(0,0,0,0.72) 0%,rgba(0,0,0,0.55) 60%,rgba(0,0,0,0.65) 100%)}
.card-bar{position:absolute;right:0;top:0;bottom:0;width:3px;background:var(--red);box-shadow:0 0 10px rgba(230,0,0,0.6)}
.card-body{position:relative;z-index:2;padding:22px 20px 20px;display:flex;flex-direction:column;align-items:center;gap:14px;color:#fff}
.card-stats-row{display:flex;align-items:center;justify-content:center;gap:18px}
.stat-item{display:flex;align-items:center;gap:5px}
.stat-item i{font-size:0.82rem;width:14px;text-align:center}
.stat-item i.ic-gift{color:#f9ca24}
.stat-item i.ic-amount{color:#ff6b6b}
.stat-item i.ic-remain{color:#74b9ff}
.stat-item-val{font-size:1rem;font-weight:700;color:#fff}
.stat-item-unit{font-size:0.68rem;color:rgba(255,255,255,0.5);margin-right:2px}
.stat-divider{width:1px;height:16px;background:rgba(255,255,255,0.2)}
.glass-row{display:inline-flex;align-items:center;gap:10px;background:rgba(255,255,255,0.08);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);border-radius:8px;padding:7px 12px;max-width:100%}
.serial-txt{font-family:monospace;font-size:0.9rem;letter-spacing:1.5px;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px}
.copy-btn{display:flex;align-items:center;justify-content:center;background:none;border:none;color:rgba(255,255,255,0.5);font-size:0.92rem;padding:0;cursor:pointer;flex-shrink:0;transition:color .2s,transform .2s var(--ease-spring)}
.copy-btn:hover{color:#55efc4;transform:scale(1.25)}
.copy-btn:active{transform:scale(0.85)}
.charge-btn{display:inline-flex;align-items:center;gap:6px;color:#ffcccc!important;text-decoration:none;font-size:0.82rem;font-weight:700;font-family:'Cairo',sans-serif;cursor:pointer;white-space:nowrap;transition:color .2s,transform .2s var(--ease-spring)}
.charge-btn i{font-size:0.78rem;color:#ff8080}
.charge-btn:hover{color:#fff!important;transform:scale(1.05)}
.charge-btn:active{transform:scale(0.96)}

/* ERROR BOX */
.no-offers,.error-msg{text-align:center;padding:28px 22px;font-size:1.1rem;border-radius:var(--radius-md);margin:30px 0;background:var(--surface);backdrop-filter:blur(16px);border:1px solid var(--border);box-shadow:var(--shadow-sm);color:var(--text-dark)}
.error-msg{color:var(--red);border-color:rgba(230,0,0,0.15);background:rgba(230,0,0,0.04)}

/* RETRY + RESET BUTTONS */
.error-actions{display:flex;flex-direction:column;align-items:center;gap:12px;margin-top:18px}
.retry-btn{display:inline-flex;align-items:center;gap:8px;background:var(--red);color:#fff!important;text-decoration:none;font-size:1rem;font-weight:700;font-family:'Cairo',sans-serif;padding:13px 32px;border-radius:var(--radius-md);box-shadow:0 4px 18px rgba(230,0,0,0.35);transition:transform .3s var(--ease-spring),box-shadow .3s;border:none;cursor:pointer;width:100%;justify-content:center}
.retry-btn:hover{transform:translateY(-3px);box-shadow:0 8px 28px rgba(230,0,0,0.5)}
.retry-btn:active{transform:scale(0.95)}
.reset-btn{display:inline-flex;align-items:center;gap:8px;background:transparent;color:var(--text-muted)!important;text-decoration:none;font-size:0.9rem;font-weight:600;font-family:'Cairo',sans-serif;padding:10px 24px;border-radius:var(--radius-md);border:1.5px solid var(--border);transition:transform .3s var(--ease-spring),border-color .3s,color .3s;cursor:pointer;width:100%;justify-content:center}
.reset-btn:hover{border-color:rgba(230,0,0,0.4);color:var(--red)!important;transform:translateY(-2px)}
.reset-btn:active{transform:scale(0.95)}
.reset-btn i,.retry-btn i{font-size:0.9rem}

/* BOTTOM NAV */
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:rgba(255,255,255,0.82);backdrop-filter:blur(20px) saturate(180%);-webkit-backdrop-filter:blur(20px) saturate(180%);border-top:1px solid rgba(0,0,0,0.06);display:flex;justify-content:space-around;padding:12px 0 14px;box-shadow:0 -8px 30px rgba(0,0,0,0.1);z-index:999}
.bottom-nav a{text-decoration:none;color:#555;transition:color .25s,transform .3s var(--ease-spring);text-align:center;font-size:0.85rem;display:flex;flex-direction:column;align-items:center;gap:4px;padding:4px 18px;border-radius:12px;position:relative}
.bottom-nav a::after{content:'';position:absolute;bottom:-2px;left:50%;transform:translateX(-50%);width:0;height:2px;border-radius:1px;background:var(--red);transition:width .3s var(--ease-spring)}
.bottom-nav a:hover{color:var(--red);transform:translateY(-4px)}
.bottom-nav a:hover::after{width:28px}
.bottom-nav i{font-size:1.9rem;display:block}

.ripple-effect{position:absolute;border-radius:50%;background:rgba(255,255,255,0.3);transform:scale(0);animation:ripple .55s linear;pointer-events:none}
@keyframes ripple{to{transform:scale(4);opacity:0}}
</style>
</head>
<body oncontextmenu="return false;">

<div class="banner">
    <span>Y</span><span>N</span><span>H</span><span>S</span><span>A</span><span>L</span><span>A</span><span>T</span>
</div>
<div class="small-logo-under-banner">
    <img src="https://tlashane.serv00.net/vo/mS.png" alt="">
</div>
<div class="ramadan-decoration">
    <img src="https://tlashane.serv00.net/vo/CRT.png" alt="" class="garland-left">
    <img src="https://tlashane.serv00.net/vo/CRT.png" alt="" class="garland-right">
</div>

<div class="container">

<?php if(empty($results)): ?>
<div class="login-content">
    <div class="logo">
        <img src="https://tlashane.serv00.net/vo/vodafone2.png" alt="TALASHNY Logo" class="custom-logo">
    </div>
    <h1 class="title">ماتخليش حاجة تفوتك</h1>
    <p class="subtitle">كروت رمضان_فرصة_ننور_بعض</p>
    <form method="post" id="loginForm">
        <div class="input-wrapper">
            <i class="fas fa-phone input-icon"></i>
            <input type="text" name="number" placeholder="رقم الموبايل" required>
        </div>
        <div class="input-wrapper">
            <i class="fas fa-lock input-icon"></i>
            <input type="password" name="password" placeholder="كلمة المرور" required>
        </div>
        <button type="submit" name="login" class="btn-login" id="loginBtn">تسجيل الدخول</button>
    </form>
</div>
<?php endif; ?>

<?php if(!empty($results)): ?>
<div class="results-wrapper" id="resultsContainer">
    <?php foreach($results as $res): ?>
    <div class="account-section">

        <?php $uid = uniqid(); ?>
        <div class="timer-container">
            <div class="flip-scene">
                <div class="flip-face" data-face="<?=$uid?>">
                    <div class="flip-corner-dot"></div>
                    <div class="flip-tag">AUTO</div>
                    <div class="flip-number" data-num="<?=$uid?>">15</div>
                </div>
            </div>
            <div class="flip-label-row">
                <div class="flip-label-line"></div>
                <div class="flip-label-text">ثانية</div>
                <div class="flip-label-line right"></div>
            </div>
        </div>

        <?php if(!empty($res['message'])): ?>
        <div class="error-msg">
            <i class="fas fa-circle-exclamation" style="font-size:1.6rem;display:block;margin-bottom:10px;opacity:0.8"></i>
            <?= htmlspecialchars($res['message']) ?>
            <div class="error-actions">
                <a href="javascript:history.back()" class="retry-btn">
                    <i class="fas fa-rotate-right"></i> إعادة المحاولة
                </a>
                <a href="https://web.vodafone.com.eg/ar/forgot-password" target="_blank" class="reset-btn">
                    <i class="fas fa-key"></i> ادخل انا فودافون غيرها
                </a>
            </div>
        </div>
        <?php endif; ?>

        <?php if($res['success'] && !empty($res['promos'])): ?>
            <?php foreach($res['promos'] as $index => $promo): ?>
            <div class="promo-card" style="--index:<?=$index?>">
                <div class="card-overlay"></div>
                <div class="card-bar"></div>
                <div class="card-body">
                    <div class="card-stats-row">
                        <div class="stat-item">
                            <i class="fas fa-coins ic-amount"></i>
                            <span class="stat-item-val"><?= htmlspecialchars($promo['amount']) ?></span>
                            <span class="stat-item-unit">جنيه</span>
                        </div>
                        <div class="stat-divider"></div>
                        <div class="stat-item">
                            <i class="fas fa-gift ic-gift"></i>
                            <span class="stat-item-val"><?= htmlspecialchars($promo['gift']) ?></span>
                            <span class="stat-item-unit">وحدة</span>
                        </div>
                        <div class="stat-divider"></div>
                        <div class="stat-item">
                            <i class="fas fa-hourglass-half ic-remain"></i>
                            <span class="stat-item-val"><?= htmlspecialchars($promo['remaining']) ?></span>
                            <span class="stat-item-unit">متبقي</span>
                        </div>
                    </div>
                    <div class="glass-row card-serial">
                        <?php $serial = (string)$promo['card_serial']; ?>
                        <span class="serial-txt"><?= htmlspecialchars($serial) ?></span>
                        <button onclick="copySerial(this)" class="copy-btn">
                            <i class="fas fa-clone"></i>
                        </button>
                    </div>
                    <?php $ussd = "*858*" . str_replace(' ', '', $serial) . "#"; ?>
                    <div class="glass-row">
                        <a href="tel:<?= htmlspecialchars($ussd) ?>" class="charge-btn">
                            <i class="fas fa-bolt"></i> شحن فوري
                        </a>
                    </div>
                </div>
            </div>
            <?php endforeach; ?>
        <?php elseif($res['success']): ?>
            <div class="no-offers">لا توجد عروض متاحة حالياً لهذا الرقم</div>
        <?php endif; ?>

    </div>
    <?php endforeach; ?>
</div>
<?php endif; ?>

</div>

<div class="bottom-nav">
    <a href="https://t.me/FY_TF" target="_blank"><i class="fab fa-telegram-plane"></i></a>
    <a href="https://wa.me/message/U6AIKBGFCNCQK1" target="_blank"><i class="fab fa-whatsapp"></i></a>
    <a href="https://www.facebook.com/VI808IV" target="_blank"><i class="fab fa-facebook-f"></i></a>
</div>

<script>
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-face]').forEach(faceEl => {
        const numEl = document.querySelector('[data-num="'+faceEl.dataset.face+'"]');
        startFlipTimer(faceEl, numEl);
    });

    const loginBtn = document.getElementById('loginBtn');
    if(loginBtn) loginBtn.addEventListener('click', e => createRipple(e, loginBtn));

    const form = document.getElementById('loginForm');
    if(form) form.addEventListener('submit', () => {
        if(loginBtn){ loginBtn.textContent='جاري التحقق...'; loginBtn.style.opacity='0.75'; loginBtn.style.pointerEvents='none'; }
    });
});

document.addEventListener('copy',        e => e.preventDefault());
document.addEventListener('cut',         e => e.preventDefault());
document.addEventListener('contextmenu', e => { if(!e.target.closest('.copy-btn')) e.preventDefault(); });

function startFlipTimer(faceEl, numEl) {
    let t = 16;
    const iv = setInterval(() => {
        t--;
        faceEl.classList.remove('flip-animate');
        void faceEl.offsetWidth;
        faceEl.classList.add('flip-animate');
        setTimeout(() => {
            numEl.textContent = t;
            const urgent = t <= 5;
            numEl.style.textShadow = urgent ? '0 0 30px rgba(255,50,50,1),0 0 60px rgba(255,0,0,0.6),0 2px 4px rgba(0,0,0,0.8)' : '';
            faceEl.style.boxShadow = urgent ? '0 10px 40px rgba(0,0,0,0.7),0 0 0 1px rgba(230,0,0,0.5),0 0 30px rgba(230,0,0,0.3),inset 0 1px 0 rgba(255,255,255,0.07)' : '';
        }, 200);
        if(t <= 0){ clearInterval(iv); setTimeout(() => location.reload(), 600); }
    }, 1000);
}

function copySerial(btn) {
    const serial = btn.closest('.card-serial').querySelector('.serial-txt').textContent.trim();
    navigator.clipboard.writeText(serial).then(() => {
        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check"></i>';
        btn.style.color = '#55efc4';
        setTimeout(() => { btn.innerHTML = orig; btn.style.color = ''; }, 1800);
    });
}

function createRipple(e, el) {
    const r = document.createElement('span');
    const rect = el.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    r.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX-rect.left-size/2}px;top:${e.clientY-rect.top-size/2}px;`;
    r.classList.add('ripple-effect');
    el.style.position = 'relative';
    el.appendChild(r);
    setTimeout(() => r.remove(), 600);
}

document.querySelectorAll('.bottom-nav a').forEach(a => {
    a.addEventListener('click', function(){
        document.querySelectorAll('.bottom-nav a').forEach(x=>x.classList.remove('active'));
        this.classList.add('active');
    });
});
</script>
</body>
</html>