// Original flat illustration (drawn for ClinieSync): an Indian mother in a kurta and saree pallu cradling her swaddled
// newborn, framed by botanical leaves. Pure SVG - crisp at any size, no external image or licence needed.
export function MotherIllustration({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 600 560" role="img" aria-label="A mother holding her newborn baby">
        <defs>
          <linearGradient id="mi-bg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#e3f5f4"/><stop offset="1" stopColor="#dbe9ff"/>
          </linearGradient>
          <linearGradient id="mi-kurta" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#f6c04d"/><stop offset="1" stopColor="#eaa936"/>
          </linearGradient>
          <linearGradient id="mi-blanket" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#b9dcf7"/><stop offset="1" stopColor="#86bdee"/>
          </linearGradient>
          <pattern id="mi-dots" width="14" height="14" patternUnits="userSpaceOnUse">
            <circle cx="7" cy="7" r="2" fill="#f7d58b"/>
          </pattern>
          <clipPath id="mi-frame"><path d="M70 70 C150 10 460 0 540 90 C610 170 600 430 540 520 L60 560 C10 450 0 140 70 70 Z"/></clipPath>
        </defs>
      
        {/* backdrop */}
        <path d="M70 70 C150 10 460 0 540 90 C610 170 600 430 540 520 L60 560 C10 450 0 140 70 70 Z" fill="url(#mi-bg)"/>
        <g clipPath="url(#mi-frame)">
          <circle cx="455" cy="150" r="74" fill="#fde7d6"/>
          <path d="M40 560 C120 470 230 455 300 470 C380 488 470 470 600 420 L600 560 Z" fill="#cfeeea"/>
      
          {/* botanical leaves (behind) */}
          <g transform="translate(120 330) rotate(-62)">
            <path d="M0 0 C40 -70 120 -95 175 -70 C150 -10 80 25 0 0 Z" fill="#0f7c80"/>
            <path d="M0 0 C60 -35 120 -55 175 -70" stroke="#7fd0c7" strokeWidth="3" fill="none"/>
          </g>
          <g transform="translate(150 470) rotate(-28)">
            <path d="M0 0 C40 -60 115 -80 160 -55 C135 -5 70 25 0 0 Z" fill="#2e9e8f"/>
            <path d="M0 0 C55 -30 110 -45 160 -55" stroke="#a7e3da" strokeWidth="3" fill="none"/>
          </g>
          <g transform="translate(470 470) rotate(-125)">
            <path d="M0 0 C40 -70 125 -95 180 -65 C150 -5 80 25 0 0 Z" fill="#0f7c80"/>
            <path d="M0 0 C60 -35 125 -52 180 -65" stroke="#7fd0c7" strokeWidth="3" fill="none"/>
          </g>
          <g transform="translate(455 360) rotate(-150)">
            <path d="M0 0 C30 -50 90 -66 130 -46 C110 -6 55 18 0 0 Z" fill="#8fd3c9"/>
          </g>
          <g transform="translate(95 250) rotate(-95)">
            <path d="M0 0 C30 -50 90 -66 130 -46 C110 -6 55 18 0 0 Z" fill="#8fd3c9"/>
          </g>
          {/* fern */}
          <g stroke="#2e9e8f" strokeWidth="4" strokeLinecap="round" fill="none">
            <path d="M505 545 C500 470 515 400 545 330"/>
            <path d="M505 500 l-26 -16 M507 470 l-26 -18 M512 440 l-24 -20 M519 410 l-22 -20 M528 382 l-20 -20"/>
            <path d="M506 492 l26 -20 M509 462 l26 -22 M515 432 l24 -22 M522 404 l22 -22 M531 376 l18 -20"/>
          </g>
          <g fill="#ffffff" opacity=".7"><circle cx="160" cy="130" r="5"/><circle cx="190" cy="105" r="3"/><circle cx="520" cy="260" r="4"/></g>
      
          {/* hair (back) */}
          <path d="M240 186 C230 112 274 80 318 86 C366 92 392 136 386 198 C384 236 394 266 412 296 C432 330 430 376 402 398
                   C408 366 396 340 374 322 C358 310 340 302 330 292 L272 292 C258 306 238 314 224 332 C208 352 204 382 216 404
                   C186 388 180 346 194 312 C208 280 244 254 240 186 Z" fill="#1b2a4a"/>
      
          {/* torso */}
          <path d="M300 262 C255 262 222 274 204 296 C186 318 180 380 178 440 L170 560 L432 560 L424 440
                   C422 380 416 318 398 296 C380 274 345 262 300 262 Z" fill="url(#mi-kurta)"/>
          {/* dupatta over the shoulder */}
          <path d="M338 262 C372 266 398 280 410 304 C424 340 430 420 436 560 L392 560 C388 470 386 380 372 330 C362 300 350 284 330 276 Z"
                fill="#d9603b"/>
          <path d="M338 262 C372 266 398 280 410 304 C424 340 430 420 436 560 L392 560 C388 470 386 380 372 330 C362 300 350 284 330 276 Z"
                fill="url(#mi-dots)" opacity=".75"/>
          <path d="M420 330 C426 400 430 470 436 560" stroke="#f3c56b" strokeWidth="5" fill="none"/>
      
          {/* neck + neckline */}
          <path d="M285 226 L315 226 L320 266 C312 284 288 284 280 266 Z" fill="#c4825e"/>
          <path d="M276 262 C286 292 314 292 324 262 C316 270 284 270 276 262 Z" fill="#b8754f"/>
          <path d="M272 262 L300 300 L328 262" fill="#c4825e"/>
      
          {/* head (tilted toward the baby) */}
          <g transform="rotate(-9 300 182)">
            <ellipse cx="300" cy="182" rx="46" ry="55" fill="#c98a65"/>
            <ellipse cx="347" cy="190" rx="8" ry="12" fill="#bd7a55"/>
            <circle cx="349" cy="207" r="5" fill="#f3c56b"/>
            {/* hair front: centre parting */}
            <path d="M252 190 C244 136 270 110 302 112 C336 114 358 138 349 190 C344 166 330 148 312 144 C306 156 296 158 290 146
                     C272 152 258 168 252 190 Z" fill="#1b2a4a"/>
            <circle cx="301" cy="172" r="3.4" fill="#c0392b"/>
          </g>
          {/* hair over the left shoulder */}
          <path d="M254 206 C242 244 238 282 250 314 C258 336 266 352 258 374 C252 360 240 350 232 330 C222 304 226 266 236 240 C242 224 248 214 254 206 Z" fill="#1b2a4a"/>
      
          {/* left arm (under the baby) */}
          <path d="M206 300 C190 330 186 380 196 410 C206 440 260 446 330 436 L332 412 C280 414 236 410 228 390 C222 372 226 340 232 312 Z" fill="#c4825e"/>
          <path d="M204 298 C196 312 190 330 188 348 L230 352 C230 334 232 318 236 304 Z" fill="#eaa936"/>
      
          {/* baby */}
          <g>
            <path d="M210 360 C214 330 260 318 320 324 C376 330 410 348 410 372 C410 398 368 414 304 412 C246 410 206 392 210 360 Z" fill="url(#mi-blanket)"/>
            <path d="M260 330 C300 350 352 352 404 360" stroke="#ffffff" strokeOpacity=".7" strokeWidth="5" fill="none" strokeLinecap="round"/>
            <path d="M232 396 C270 404 320 406 380 398" stroke="#6fa9e0" strokeWidth="3" fill="none" strokeLinecap="round"/>
            <path d="M196 352 C188 314 214 296 240 298 C268 300 282 322 278 352 C266 380 214 384 196 352 Z" fill="#d7ebfb"/>
            <circle cx="234" cy="342" r="28" fill="#e6b089"/>
            <path d="M212 330 C216 316 232 310 246 316 C238 316 236 320 237 324 C228 320 218 322 212 330 Z" fill="#2a3552"/>
            <path d="M222 350 q6 4 12 0" stroke="#a0603e" strokeWidth="2.4" fill="none" strokeLinecap="round"/>
            <circle cx="244" cy="340" r="3" fill="#e9877a" opacity=".55"/>
            <ellipse cx="272" cy="358" rx="10" ry="8" fill="#e6b089"/>
          </g>
      
          {/* right arm (over the baby) */}
          <path d="M396 300 C414 332 420 380 410 404 C398 430 350 420 296 392 L306 370 C348 386 380 392 386 380 C392 366 384 334 372 312 Z" fill="#c98a65"/>
          <path d="M398 296 C410 314 418 334 420 356 L374 362 C374 342 370 322 362 306 Z" fill="#d9603b"/>
          <path d="M398 296 C410 314 418 334 420 356 L374 362 C374 342 370 322 362 306 Z" fill="url(#mi-dots)" opacity=".75"/>
          <path d="M374 362 L420 356" stroke="#f3c56b" strokeWidth="5"/>
          <ellipse cx="300" cy="380" rx="18" ry="13" fill="#c98a65" transform="rotate(-20 300 380)"/>
          <path d="M296 392 l-4 -10 M306 389 l-3 -11" stroke="#b37452" strokeWidth="2" strokeLinecap="round"/>
          <path d="M396 396 C402 402 410 402 414 396" stroke="#f3c56b" strokeWidth="5" fill="none"/>
        </g>
    </svg>
  );
}
