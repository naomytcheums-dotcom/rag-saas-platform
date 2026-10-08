/* eslint-disable @next/next/no-img-element -- generated from the Figma "AI SaaS Website Design" export; the artwork is positioned absolutely at 1440px. */
"use client";

import Link from "next/link";
import LanguageMenu from "@/components/LanguageMenu";
import { useTranslation } from "@/lib/i18n";
import Stage from "./Stage";

const img2B9Gp2GJnBjBx44Yovd3HRxqiXmPng = "/landing/figma/img2B9Gp2GJnBjBx44Yovd3HRxqiXmPng.png";
const img38I07RfLj4Dxjrqz7YxCanY6KoPng = "/landing/figma/img38I07RfLj4Dxjrqz7YxCanY6KoPng.png";
const imgB9Rol6BhEmArgbWauFiEj7UzzjyPng = "/landing/figma/imgB9Rol6BhEmArgbWauFiEj7UzzjyPng.png";
const imgImage = "/landing/figma/imgImage.png";
const imgImage1 = "/landing/figma/imgImage1.svg";
const imgImage2 = "/landing/figma/imgImage2.svg";
const imgImage3 = "/landing/figma/imgImage3.svg";
const imgImage85 = "/landing/figma/imgImage85.png";
const imgLFzmQ3NzC3Lg6Q2C7LvBf8KwPng = "/landing/figma/imgLFzmQ3NzC3Lg6Q2C7LvBf8KwPng.png";
const imgLine64 = "/landing/figma/imgLine64.svg";
const imgMEibgBqwotHj35YaPhM5LjuLc2UPng = "/landing/figma/imgMEibgBqwotHj35YaPhM5LjuLc2UPng.png";
const imgSvg = "/landing/figma/imgSvg.svg";
const imgSvg1 = "/landing/figma/imgSvg1.svg";
const imgSvg2 = "/landing/figma/imgSvg2.svg";

/** Splits the translated second hero line so that its first two words get the orange accent of the reference ("Intelligence"). */
function useHeadline() {
  const { t } = useTranslation();
  const first = t("landing.hero.title_line1");
  const words = t("landing.hero.title_line2").split(" ");
  return { first, accent: words.slice(0, 2).join(" "), rest: words.slice(2).join(" ") };
}

/** Hero + navigation + figures strip: 1440 x 972 design stage, exported from Figma, scaled to the viewport. */
export default function HeroStage() {
  const { t } = useTranslation();
  const headline = useHeadline();
  return (
    <section id="top">
      <Stage width={1440} height={972}>
        <div className="relative h-[972px] w-[1440px] overflow-hidden bg-[#010101] text-white">
<div className="absolute contents left-[-289px] top-[-239px]" data-node-id="1:39" data-name="Hero-Section">
        <div className="-translate-x-1/2 absolute contents left-[calc(50%+429.46px)] top-[-239px]" data-node-id="1:40">
          <div className="-translate-x-1/2 absolute flex h-[1223.643px] items-center justify-center left-[calc(50%+906.96px)] top-[-239px] w-[1921.91px]" data-node-id="1:41">
            <div className="-rotate-90 -scale-y-100 flex-none">
              <div className="h-[1921.91px] relative w-[1223.643px]" data-name="image 85">
                <img alt="" className="absolute inset-0 max-w-none object-cover pointer-events-none size-full" src={imgImage85} />
              </div>
            </div>
          </div>
          <div className="-translate-x-1/2 absolute flex h-[1223.643px] items-center justify-center left-[calc(50%-531.45px)] top-[-239px] w-[955.09px]" data-node-id="1:42">
            <div className="-rotate-90 flex-none">
              <div className="h-[955.09px] relative w-[1223.643px]" data-name="image 87">
                <div className="absolute inset-0 overflow-hidden pointer-events-none">
                  <img alt="" className="absolute h-[211.13%] left-0 max-w-none top-[-106.18%] w-full" src={imgImage85} />
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="absolute contents left-[41px] top-[-16px]" data-node-id="1:43">
          <div className="absolute contents left-[41px] top-[-16px]" data-node-id="1:44">
            <div className="absolute h-[481px] left-[240px] opacity-35 top-[119px] w-[319px]" data-node-id="1:45" data-name="image">
              <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <img alt="" className="absolute left-0 max-w-none size-full top-0" src={imgImage} />
              </div>
            </div>
            <div className="absolute h-[481px] left-[41px] opacity-22 top-[-16px] w-[319px]" data-node-id="1:46" data-name="image">
              <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <img alt="" className="absolute left-0 max-w-none size-full top-0" src={imgImage} />
              </div>
            </div>
            <div className="absolute h-[481px] left-[654px] opacity-22 top-[-12px] w-[319px]" data-node-id="1:47" data-name="image">
              <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <img alt="" className="absolute left-0 max-w-none size-full top-0" src={imgImage} />
              </div>
            </div>
            <div className="absolute h-[481px] left-[981px] opacity-22 top-[-1px] w-[319px]" data-node-id="1:48" data-name="image">
              <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <img alt="" className="absolute left-0 max-w-none size-full top-0" src={imgImage} />
              </div>
            </div>
            <div className="absolute flex h-[319px] items-center justify-center left-[698px] top-[477px] w-[481px]" data-node-id="1:49">
              <div className="flex-none rotate-90">
                <div className="h-[481px] opacity-22 relative w-[319px]" data-name="image">
                  <div className="absolute inset-0 overflow-hidden pointer-events-none">
                    <img alt="" className="absolute left-0 max-w-none size-full top-0" src={imgImage} />
                  </div>
                </div>
              </div>
            </div>
            <div className="absolute flex h-[319px] items-center justify-center left-[194px] top-[477px] w-[481px]" data-node-id="1:50">
              <div className="flex-none rotate-90">
                <div className="h-[481px] opacity-22 relative w-[319px]" data-name="image">
                  <div className="absolute inset-0 overflow-hidden pointer-events-none">
                    <img alt="" className="absolute left-0 max-w-none size-full top-0" src={imgImage} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="absolute content-stretch flex flex-col gap-[27px] items-center left-[217px] top-[210.26px] w-[1005px]" data-node-id="1:51" data-name="HeroSection-Content">
          <div className="bg-gradient-to-r border-[0.943px] border-[rgba(255,255,255,0.15)] border-solid content-stretch flex from-[rgba(255,84,31,0.13)] gap-[13.196px] items-center px-[23.564px] py-[15.081px] relative rounded-[50.898px] shrink-0 to-[rgba(255,84,31,0.04)]" data-node-id="1:52">
            <div className="h-[45.326px] relative shrink-0 w-[151.841px]" data-node-id="1:53" data-name="Container">
              <div className="absolute inset-[2.27px_111.05px_2.27px_0] overflow-clip rounded-[1132.008px]" data-node-id="1:54" data-name="Container">
                <div className="absolute inset-0 rounded-[1132.008px]" data-node-id="1:55" data-name="mEIBGBqwotHJ35YaPhM5ljuLc2U.png">
                  <div className="absolute inset-0 overflow-hidden pointer-events-none rounded-[1132.008px]">
                    <img alt="" className="absolute left-0 max-w-none size-full top-0" src={imgMEibgBqwotHj35YaPhM5LjuLc2UPng} />
                  </div>
                </div>
                <div className="absolute border-[1.133px] border-[rgba(255,255,255,0.1)] border-solid inset-0 rounded-[1132.008px]" data-node-id="1:56" data-name="Border" />
              </div>
              <div className="absolute inset-[2.27px_83.85px_2.27px_27.2px] overflow-clip rounded-[1132.008px]" data-node-id="1:57" data-name="Container">
                <div className="absolute inset-0 rounded-[1132.008px]" data-node-id="1:58" data-name="2B9gp2gJnBjBX44Yovd3HRxqiXM.png">
                  <div className="absolute inset-0 overflow-hidden pointer-events-none rounded-[1132.008px]">
                    <img alt="" className="absolute left-0 max-w-none size-full top-0" src={img2B9Gp2GJnBjBx44Yovd3HRxqiXmPng} />
                  </div>
                </div>
                <div className="absolute border-[1.133px] border-[rgba(255,255,255,0.1)] border-solid inset-0 rounded-[1132.008px]" data-node-id="1:59" data-name="Border" />
              </div>
              <div className="absolute inset-[2.27px_56.65px_2.27px_54.39px] overflow-clip rounded-[1132.008px]" data-node-id="1:60" data-name="Container">
                <div className="absolute inset-0 rounded-[1132.008px]" data-node-id="1:61" data-name="B9ROL6BhEMArgbWauFiEj7UZZJY.png">
                  <div className="absolute inset-0 overflow-hidden pointer-events-none rounded-[1132.008px]">
                    <img alt="" className="absolute left-0 max-w-none size-full top-0" src={imgB9Rol6BhEmArgbWauFiEj7UzzjyPng} />
                  </div>
                </div>
                <div className="absolute border-[1.133px] border-[rgba(255,255,255,0.1)] border-solid inset-0 rounded-[1132.008px]" data-node-id="1:62" data-name="Border" />
              </div>
              <div className="absolute inset-[2.27px_27.2px_2.27px_83.85px] overflow-clip rounded-[1132.008px]" data-node-id="1:63" data-name="Container">
                <div className="absolute inset-0 rounded-[1132.008px]" data-node-id="1:64" data-name="lFzmQ3NzC3LG6q2c7lvBf8kw.png">
                  <div className="absolute inset-0 overflow-hidden pointer-events-none rounded-[1132.008px]">
                    <img alt="" className="absolute left-0 max-w-none size-full top-0" src={imgLFzmQ3NzC3Lg6Q2C7LvBf8KwPng} />
                  </div>
                </div>
                <div className="absolute border-[1.133px] border-[rgba(255,255,255,0.1)] border-solid inset-0 rounded-[1132.008px]" data-node-id="1:65" data-name="Border" />
              </div>
              <div className="absolute inset-[2.27px_0_2.27px_111.05px] overflow-clip rounded-[1132.008px]" data-node-id="1:66" data-name="Container">
                <div className="absolute inset-0 rounded-[1132.008px]" data-node-id="1:67" data-name="38I07rfLJ4DXJRQZ7YXCanY6ko.png">
                  <div className="absolute inset-0 overflow-hidden pointer-events-none rounded-[1132.008px]">
                    <img alt="" className="absolute left-0 max-w-none size-full top-0" src={img38I07RfLj4Dxjrqz7YxCanY6KoPng} />
                  </div>
                </div>
                <div className="absolute border-[1.133px] border-[rgba(255,255,255,0.1)] border-solid inset-0 rounded-[1132.008px]" data-node-id="1:68" data-name="Border" />
              </div>
            </div>
            <div className="h-[42.142px] overflow-clip relative shrink-0 w-[440px]" data-node-id="1:69" data-name="Container">
              <div className="hidden absolute h-[15.864px] left-0 overflow-clip top-0 w-[83.852px]" data-node-id="1:70" data-name="Container">
                <div className="absolute left-0 size-[15.864px] top-0" data-node-id="1:71" data-name="Image">
                  <div className="absolute left-0 overflow-clip size-[15.864px] top-0" data-node-id="1:72" data-name="image fill">
                    <div className="absolute left-0 size-[15.864px] top-0" data-node-id="1:73" data-name="image">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgImage1} />
                    </div>
                  </div>
                </div>
                <div className="absolute inset-[0_67.99px_0_0]" data-node-id="1:75" data-name="SVG">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSvg} />
                </div>
                <div className="absolute left-[17px] size-[15.864px] top-0" data-node-id="1:78" data-name="Image">
                  <div className="absolute left-0 overflow-clip size-[15.864px] top-0" data-node-id="1:79" data-name="image fill">
                    <div className="absolute left-0 size-[15.864px] top-0" data-node-id="1:80" data-name="image">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgImage2} />
                    </div>
                  </div>
                </div>
                <div className="absolute inset-[0_50.99px_0_17px]" data-node-id="1:82" data-name="SVG">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSvg1} />
                </div>
                <div className="absolute left-[33.99px] size-[15.864px] top-0" data-node-id="1:85" data-name="Image">
                  <div className="absolute left-0 overflow-clip size-[15.864px] top-0" data-node-id="1:86" data-name="image fill">
                    <div className="absolute left-0 size-[15.864px] top-0" data-node-id="1:87" data-name="image">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgImage1} />
                    </div>
                  </div>
                </div>
                <div className="absolute inset-[0_34px_0_33.99px]" data-node-id="1:89" data-name="SVG">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSvg} />
                </div>
                <div className="absolute left-[50.99px] size-[15.864px] top-0" data-node-id="1:92" data-name="Image">
                  <div className="absolute left-0 overflow-clip size-[15.864px] top-0" data-node-id="1:93" data-name="image fill">
                    <div className="absolute left-0 size-[15.864px] top-0" data-node-id="1:94" data-name="image">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgImage1} />
                    </div>
                  </div>
                </div>
                <div className="absolute inset-[0_17px_0_50.99px]" data-node-id="1:96" data-name="SVG">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSvg} />
                </div>
                <div className="absolute left-[67.99px] size-[15.864px] top-0" data-node-id="1:99" data-name="Image">
                  <div className="absolute left-0 overflow-clip size-[15.864px] top-0" data-node-id="1:100" data-name="image fill">
                    <div className="absolute left-0 size-[15.864px] top-0" data-node-id="1:101" data-name="image">
                      <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgImage3} />
                    </div>
                  </div>
                </div>
                <div className="absolute inset-[0_0_0_67.99px]" data-node-id="1:103" data-name="SVG">
                  <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgSvg2} />
                </div>
              </div>
              <p className="[word-break:break-word] absolute font-normal h-auto leading-[21.756px] left-0 not-italic text-[16.855px] text-[rgba(255,255,255,0.65)] top-[11px] tracking-[-0.3626px] w-auto whitespace-nowrap" data-node-id="1:106">
{t("landing.hero.badge")}
</p>
            </div>
          </div>
          <p className="[word-break:break-word] font-bold leading-[0] min-w-full not-italic relative shrink-0 text-[72px] text-center text-white w-[min-content]" data-node-id="1:107">
<span className="leading-[80px]">{headline.first}{" "}</span>
<span className="leading-[80px] text-[#ff541f]">{headline.accent}</span>
<span className="leading-[80px]">{headline.rest ? " " + headline.rest : ""}</span>
</p>
          <p className="[word-break:break-word] font-normal leading-[normal] not-italic relative shrink-0 text-[22px] text-[rgba(255,255,255,0.7)] text-center w-[860px]" data-node-id="1:108">
{t("landing.hero.subtitle")}
</p>
          <div className="content-stretch flex gap-[23px] items-center relative shrink-0" data-node-id="1:109">
            <Link href="/register" className="contents"><div className="bg-[#ff541f] content-stretch flex items-center justify-center overflow-clip px-[35px] py-[15px] relative rounded-[10px] shrink-0" data-node-id="1:110" data-name="Link">
              <div className="[word-break:break-word] flex flex-col font-bold justify-center leading-[0] not-italic relative shrink-0 text-[20px] text-white whitespace-nowrap" data-node-id="1:111"><p className="leading-[19.2px]">{t("landing.cta.start")}</p></div>
            </div></Link>
            <Link href="/chat" className="contents"><div className="border border-[rgba(252,252,252,0.23)] border-solid content-stretch flex items-center justify-center overflow-clip px-[35px] py-[15px] relative rounded-[10px] shrink-0" data-node-id="1:112" data-name="Link">
              <div className="[word-break:break-word] flex flex-col font-normal justify-center leading-[0] not-italic relative shrink-0 text-[20px] text-white whitespace-nowrap" data-node-id="1:113"><p className="leading-[19.2px]">{t("landing.cta.demo")}</p></div>
            </div></Link>
          </div>
        </div>
      </div>
<div className="-translate-x-1/2 absolute content-stretch flex gap-[120px] items-center left-1/2 top-[50px]" data-node-id="1:168" data-name="Navigation">
        <div className="flex items-center justify-center relative shrink-0" data-node-id="1:169">
          <span className="text-[26px] font-bold tracking-wide text-white">RAG SaaS Platform</span>
        </div>
        <div className="content-stretch flex gap-[65px] items-start relative shrink-0" data-node-id="1:171" data-name="Nav-Links">
          <div className="content-stretch flex flex-col items-center relative shrink-0 w-[58px]" data-node-id="1:172">
            <p className="[word-break:break-word] font-bold leading-[normal] not-italic relative shrink-0 text-[22px] text-white whitespace-nowrap" data-node-id="1:173">
<a href="#top">{t("landing.nav.home")}</a>
</p>
            <div className="bg-[#ff541f] h-[2px] relative rounded-[1.5px] shrink-0 w-full" data-node-id="1:174" />
          </div>
          <p className="[word-break:break-word] font-normal leading-[normal] not-italic relative shrink-0 text-[22px] text-white whitespace-nowrap" data-node-id="1:175">
<a href="#features">{t("landing.nav.features")}</a>
</p>
          <p className="[word-break:break-word] font-normal leading-[normal] not-italic relative shrink-0 text-[22px] text-white whitespace-nowrap" data-node-id="1:176">
<a href="#pricing">{t("landing.footer.pricing")}</a>
</p>
          <p className="[word-break:break-word] font-normal leading-[normal] not-italic relative shrink-0 text-[22px] text-white whitespace-nowrap" data-node-id="1:177">
<a href="#faq">{t("landing.nav.faq")}</a>
</p>
        </div>
        <div className="flex items-center gap-6"><LanguageMenu tone="dark" /><Link href="/login" className="contents"><div className="bg-[#ff541f] content-stretch flex items-center justify-center overflow-clip px-[35px] py-[15px] relative rounded-[10px] shrink-0" data-node-id="1:178" data-name="Link">
          <div className="[word-break:break-word] flex flex-col font-bold justify-center leading-[0] not-italic relative shrink-0 text-[20px] text-white whitespace-nowrap" data-node-id="1:179">
            <p className="leading-[19.2px]">{t("landing.login")}</p>
          </div>
        </div></Link></div>
      </div>
<div className="-translate-x-1/2 absolute bg-gradient-to-b from-[5.582%] from-[rgba(0,0,0,0)] h-[372px] left-1/2 to-1/2 to-black top-[692px] w-[1440px]" data-node-id="1:180" />
<div className="-translate-x-1/2 absolute border border-[rgba(255,255,255,0.1)] border-solid h-[214px] left-1/2 overflow-clip top-[758px] w-[1440px]" data-node-id="1:181" data-name="Stats">
        <div className="[word-break:break-word] absolute contents leading-[normal] left-[170px] not-italic text-center top-[59px]" data-node-id="1:182">
          <p className="-translate-x-1/2 absolute font-normal left-[240px] text-[#ff541f] text-[23px] top-[60px] whitespace-nowrap" data-node-id="1:183">
{t("landing.stats.endpoints")}
</p>
          <p className="-translate-x-1/2 absolute font-bold left-[240.5px] text-[46px] text-white top-[101px] whitespace-nowrap" data-node-id="1:184">
900+
</p>
        </div>
        <div className="[word-break:break-word] absolute contents leading-[normal] left-[1129px] not-italic text-center top-[59px] whitespace-nowrap" data-node-id="1:185">
          <p className="-translate-x-1/2 absolute font-normal left-[1208.5px] text-[#ff541f] text-[23px] top-[60px]" data-node-id="1:186">
{t("landing.stats.integrations")}
</p>
          <p className="-translate-x-1/2 absolute font-bold left-[1208px] text-[46px] text-white top-[101px]" data-node-id="1:187">
3
</p>
        </div>
        <div className="[word-break:break-word] absolute contents leading-[normal] left-[667px] not-italic text-center top-[59px] whitespace-nowrap" data-node-id="1:188">
          <p className="-translate-x-1/2 absolute font-normal left-[719px] text-[#ff541f] text-[23px] top-[60px]" data-node-id="1:189">
{t("landing.stats.languages")}
</p>
          <p className="-translate-x-1/2 absolute font-bold left-[719.5px] text-[46px] text-white top-[101px]" data-node-id="1:190">
6
</p>
        </div>
        <div className="-translate-y-1/2 absolute flex h-[134px] items-center justify-center left-[479px] top-1/2 w-0" data-node-id="1:191">
          <div className="-rotate-90 flex-none">
            <div className="h-0 relative w-[134px]">
              <div className="absolute inset-[-2px_0_0_0]">
                <img alt="" className="block max-w-none size-full" src={imgLine64} />
              </div>
            </div>
          </div>
        </div>
        <div className="-translate-y-1/2 absolute flex h-[134px] items-center justify-center left-[959px] top-1/2 w-0" data-node-id="1:192">
          <div className="-rotate-90 flex-none">
            <div className="h-0 relative w-[134px]">
              <div className="absolute inset-[-2px_0_0_0]">
                <img alt="" className="block max-w-none size-full" src={imgLine64} />
              </div>
            </div>
          </div>
        </div>
      </div>
        </div>
      </Stage>
    </section>
  );
}
