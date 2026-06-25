import { promises as fs } from "node:fs"
import path from "node:path"

const OUT = path.resolve("quartz/static/wheel")
await fs.mkdir(OUT, { recursive: true })

// name -> recraft image url
const EMBLEMS = {
  // authors
  "author-shakespeare": "https://img.recraft.ai/GL6fimvrNLwIQeJHKGeSPqjZr-A2jeFWL9iroPLaatE/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/4ac7e79f-688b-41ab-bbca-aa1fbb95baed",
  "author-dickinson": "https://img.recraft.ai/gxnbti9vkDl6IdJ3ZFAIC5czdJMzQn2z59fZ1IZ7J9o/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/350c1650-0340-4495-aec1-5d935f572c0a",
  "author-whitman": "https://img.recraft.ai/-YJcfKFpm9p3IIJxfm1eq4DF0ZIKGWzsc-yhuadFcIQ/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/449594b1-81cb-4ff5-8f98-0532a645c932",
  "author-poe": "https://img.recraft.ai/nCb8rpa4bUaWpkYQE2pJKmRCDuHDgZv0lzHldcQ5Mww/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/d3251243-9803-483f-8e6b-95f8e25765dd",
  "author-dickens": "https://img.recraft.ai/o0WxilPBlp6nv2-KP2IWwu6OmxcScO4F586r2MRtfT8/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/5dab5bf5-1727-451b-992b-d13710c6d27e",
  "author-keats": "https://img.recraft.ai/agimHaSvP9ASXrdyRkNBX7NFX8gl7oelp2lBL3womxg/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/2afe0242-844a-40ba-a7e8-bf2eac72d00a",
  "author-chesterton": "https://img.recraft.ai/jOv9xGTYmAjLvCrwqZhycAlleOG31PpuU7UU6Aps5fc/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/bfaa1be1-51a1-4e9d-9999-520ccdd04601",
  "author-eliot": "https://img.recraft.ai/r6bC1XPVzaznOi_cYjxg3JDnIPqDeAl1c59jw6Xw5CQ/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/e952e199-b109-4e36-8a6d-94b86e48211b",
  "author-coleridge": "https://img.recraft.ai/2Z3ANX9j8VbBFM1WPvs6WXDuFxxtu4vwSktKYPkrEEU/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/2013a6f4-aa3e-4623-8cee-cacd24496ed3",
  "author-wilde": "https://img.recraft.ai/xeToEtyy7uIGQfgU2imj6JY4XmurPXlokitxb_TztpY/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/55135dec-4f2f-403b-acff-75a0edb53cc1",
  "author-austen": "https://img.recraft.ai/ifUl_EoHsTQV9C_YBmBl31MkSEw09kSSExKXibC3OG0/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/992a63f3-77f2-4869-9b28-25d7571a813a",
  "author-bronte": "https://img.recraft.ai/bQjWMV9E21DsWfXoUDVjlSeXxpvloxS9X4FqKhaJqrg/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/9b5bf9d4-2e23-47dc-b52b-606ed5396d84",
  "author-hemingway": "https://img.recraft.ai/Z_4_LA-PkjlZzBBDoYBmOAPkF6t-9t6v5eqhJtYhtQo/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/ecb5853d-656b-4217-98ad-c55c15dbfa48",
  // axes
  "axis-topoi": "https://img.recraft.ai/vr8cBfypeEOnM14ILfVJXtLixInjNLSKvyngekRX8nA/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/81873823-aa82-4c29-aa23-c7888f4bcd9f",
  "axis-archetipi": "https://img.recraft.ai/fme23kRY1SHSG49kNZYpVieDIZpALVloXvc2hLqIfTo/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/b4f140ff-6db6-4950-bcbe-27dc0c960dd2",
  "axis-motivi": "https://img.recraft.ai/n_CE1Gui3vwE82ytLyqr08NDoBCJxpEHykS0-DJPTg8/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/6d9c307b-7a2a-4b9a-8c74-9174a9b901d0",
  "axis-concetti": "https://img.recraft.ai/qeyJG04Jtrh_LJb2bVtUxe2347pbKGoMFjhL08QmgPE/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/eaeb020e-49b7-40cb-be8a-075a22bbfec3",
  "axis-forme": "https://img.recraft.ai/_aQRY7ygwWPrgINn9kOHIJL0maA-V8temYTvaTJnYik/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/9549d046-c15b-4b62-979a-bf93770bdd21",
  "axis-storia": "https://img.recraft.ai/sN4PCxEp2wKh8kB89STvpj4sti8xLmduthLSKjyyreE/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/757b3f59-9edd-41e0-91c2-7d4de5ed09fe",
  "axis-ambientazioni": "https://img.recraft.ai/ymo9KGJNt3vZKR259UemeADPtzwQ-aqVeUA1c1990XQ/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/3c4c2a45-bd1a-4e46-b8e0-1534bc122d65",
  "axis-personaggi": "https://img.recraft.ai/4xgVktNtVrtKzUzwYwtQMzOIwjeuGn6JxCiP-4wkGw8/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/9affcb6e-07b9-448e-8e49-6513aacb381e",
  // clusters
  "cluster-death": "https://img.recraft.ai/nmQT7uVhnWAmohrXFAVa0KLXd2e5ff1CZCa2WD0jFtI/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/1b80aae4-c21f-4202-97af-39ce85be8d75",
  "cluster-love": "https://img.recraft.ai/yiPs_so5EiGj230eC5EiNYHze7EphVLl8uid0KUj3xI/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/6a7029d2-b1e6-4bef-a39c-30a56d39415f",
  "cluster-grief": "https://img.recraft.ai/Uy8ZCXUQkEVnB8_WIS3Kd7QAueQhNtfnWfGP8mNry2Q/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/bd86a2c5-904e-4d52-a324-ce4ee2b6361b",
  "cluster-sonnet": "https://img.recraft.ai/0MGAC8isvlz0P3X6TNQNEBJYTiVhCozrfO8MGJaACRg/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/f3cf8f44-6e43-4c8c-90d5-2a44e738229e",
  "cluster-wonder": "https://img.recraft.ai/ETs8duIykfDLgBzKe6y8totp9lbU-8AQN270PM7Z7n4/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/fae10201-f98c-40ab-9703-b653354b13d4",
  "cluster-satire": "https://img.recraft.ai/Mp_zZvCQmOdvIyguJNRBj0O6GRrr5bc7hYhE6zGoWmc/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/7f808fec-f2b1-4852-82c1-657a5a1117bf",
  "cluster-transience": "https://img.recraft.ai/hwFXFe2tn4yZ8qbr4LIO8QG3JS8X3kuCLClzKlv6zkc/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/c3eb8641-8dcb-42cc-b9f1-d2a3f5714b89",
  "cluster-lyric": "https://img.recraft.ai/t_AqU8ja_7Z-xG4p57MiSux7_IKq3HP5KuAsctAeq8Q/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/396e99cf-6246-4b3e-a577-aedc50624d3f",
  "cluster-money": "https://img.recraft.ai/I0JWQf_tXYp0UH48dt7_Pnq84mrxd2aIZen4X9L9bDk/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/f6847f4b-90ff-47f9-96f9-28b906e3b82f",
  "cluster-seasons": "https://img.recraft.ai/txu26gBl76Uk-wlt2LKcvJG16Z_vt2w6nSJxMDz53po/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/97939906-26f2-4379-b975-cd4586a9c456",
  "cluster-nature": "https://img.recraft.ai/ACrnCn4huEpP-XAcPpmo-HmHbIbJCeUNbwgH6Wi_QZg/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/22fc5482-137c-4a45-8eec-ba0e7d28eea8",
  "cluster-sea": "https://img.recraft.ai/vqG7xFTlNfkpkv_90jyavSPWk6er7aHnb1hdcCBVXUM/rs:fit:1024:1024:0/raw:1/plain/abs://external/images/428f5012-f085-41ef-918a-62f49735e77d",
}

let ok = 0
for (const [name, url] of Object.entries(EMBLEMS)) {
  const res = await fetch(url)
  if (!res.ok) {
    console.error("FAIL", name, res.status)
    continue
  }
  const buf = Buffer.from(await res.arrayBuffer())
  await fs.writeFile(path.join(OUT, name + ".png"), buf)
  ok++
}
console.log(`downloaded ${ok}/${Object.keys(EMBLEMS).length} emblems to ${OUT}`)
