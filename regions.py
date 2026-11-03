import re

# Trading regions as brokers use them, with the ports and area names seen in real circulars.
# Not exhaustive: an unknown port gives no location score rather than a bad one.
REGIONS = {
    "Black Sea": "black sea, bsea, b.sea, danube, constanta, varna, bourgas, burgas, novorossiysk, novo, tuapse, odessa, "
                 "odesa, chornomorsk, izmail, reni, galati, galatz, braila, giurgiulesti, giurgiuleshti, giurguleshti, "
                 "tulcea, sulina, samsun, bartin, eregli, zonguldak, poti, batumi, orlivka, kherson, mykolaiv, georgia, "
                 "romania, bulgaria, ukraine, russia black sea, turkish black sea",
    "Marmara/Aegean": "marmara, marmara sea, tbs, gemlik, izmit, izmit bay, nemrut, aliaga, izmir, bandirma, tekirdag, "
                      "istanbul, karasu, gulluk, piraeus, piraeus roads, thessaloniki, volos, psachna, chalkis, corinth, "
                      "greece, aegean",
    "East Med": "east med, e.med, emed, eastern med, iskenderun, mersin, alexandria, damietta, port said, abu kir, "
                "el-arish, el arish, beirut, latakia, tartous, haifa, ashdod, limassol, famagusta, cyprus, syria, "
                "lebanon, egypt, egypt med, israel, turkey",
    "Central Med": "central med, cmed, c.med, med, italy, ec italy, ravenna, marghera, porto marghera, venice, "
                   "porto nogaro, monfalcone, ancona, bari, genova, genoa, sibenik, split, rijeka, koper, adriatic, "
                   "durres, albania, porto romano, bizerte, sousse, sfax, tunis, tunisia, misurata, libya, tobruk, "
                   "benghazi, malta, sicily",
    "West Med": "west med, wmed, w.med, spain med, tarragona, barcelona, valencia, cartagena, seville, huelva, "
                "algeria, bejaia, djen djen, oran, marseille, gibraltar",
    "Atlantic Iberia/NW Africa": "lisbon, la coruna, figueira da foz, casablanca, agadir, jorf lasfar, safi, morocco, "
                                 "dakar, las palmas, la palmas, canaries, portugal, ushant",
    "Continent/UK": "continent, ara, antwerp, rotterdam, amsterdam, hamburg, bremen, brake, brake-bremen, dunkirk, ghent, "
                    "terneuzen, le havre, rouen, uk, east coast uk, west coast uk, great yarmouth, erith, hull, "
                    "sharpness, cork, ireland, skaw, netherlands, belgium, germany, france",
    "Baltic/Scandinavia": "baltic, szczecin, stettin, swinoujscie, gdynia, gdansk, riga, klaipeda, st petersburg, "
                          "ust-luga, ust luga, üst_luga, rostock, koege, avedore, naantali, turku, uddevalla, "
                          "norrsundet, sweden, finland, denmark, poland",
    "West Africa": "west africa, waf, tema, takoradi, abidjan, lagos, doula, douala, monrovia, luanda, nouakchott, "
                   "conakry, kamsar, ghana, nigeria, angola, navico jetty",
    "Red Sea": "red sea, red, jeddah, yanbu, aqaba, port sudan, sudan, djibouti, suez, adabiya, king abdullah, hodeidah",
    "Arabian Gulf": "arabian gulf, ag, pg, persian gulf, jebel ali, dammam, kuwait, umm qasr, basrah, bandar abbas, "
                    "sharjah, hamriyah, fujairah, khor fakkan, sohar, oman, duqm, uae, iraq, sitrah, qatar, ruwais, "
                    "hormuz, inside hormuz, outside hormuz",
    "India/Pakistan": "india, wci, eci, e.c. india, kandla, mundra, mumbai, nhava sheva, hazira, haldia, paradip, "
                      "vizag, visakhapatnam, chennai, krishnapatnam, karwar, goa, karachi, bin qasim, pakistan, pak, "
                      "colombo, sri lanka, chittagong, bangladesh, mongla, maldives",
    "SE Asia": "se asia, se.asia, seasia, south east asia, southeast asia, singapore, spore, port kelang, port klang, "
               "kuantan, surabaya, jakarta, cjk, sulawesi, kalimantan, indonesia, malaysia, bangkok, kosichang, "
               "songkhla, phuket, thailand, vietnam, ho chi minh, phu my, philippines, phillipines, phillipine, "
               "philippine, phil, subic, subic bay, manila, bacolod",
    "Far East": "far east, fe, f'east, feast, china, n china, n.china, north china, s china, qingdao, tianjin, shanghai, "
                "ningbo, rizhao, lianyungang, laizhou, zhangjiagang, jingjiang, jingtang, caofeidian, beihai, qinzhou, "
                "fangcheng, dongguan, shekou, huangpu, yantai, longkou, shandong, kaohsiung, taiwan, hong kong, japan, "
                "korea, ulsan, busan, donghae, mokpo",
    "East/South Africa": "east africa, mombasa, dar es salaam, maputo, beira, mozambique, mtwara, mtawara, tanzania, "
                         "kenya, durban, richards bay, south africa",
    "Americas": "us gulf, usg, houston, new orleans, galveston, usa, canada, vancouver, caribbean, carib, venezuela, "
                "petro cedeno terminal, panama, balboa, santos, paranagua, brazil, recalada, ecsa, argentina",
    "Australia": "australia, port hedland, newcastle, dampier, gladstone",
}

NEIGHBOURS = {
    "Black Sea": {"Marmara/Aegean"},
    "Marmara/Aegean": {"Black Sea", "East Med", "Central Med"},
    "East Med": {"Marmara/Aegean", "Central Med", "Red Sea"},
    "Central Med": {"Marmara/Aegean", "East Med", "West Med"},
    "West Med": {"Central Med", "Atlantic Iberia/NW Africa"},
    "Atlantic Iberia/NW Africa": {"West Med", "Continent/UK", "West Africa"},
    "Continent/UK": {"Baltic/Scandinavia", "Atlantic Iberia/NW Africa"},
    "Baltic/Scandinavia": {"Continent/UK"},
    "West Africa": {"Atlantic Iberia/NW Africa"},
    "Red Sea": {"East Med", "Arabian Gulf", "East/South Africa"},
    "Arabian Gulf": {"Red Sea", "India/Pakistan"},
    "India/Pakistan": {"Arabian Gulf", "SE Asia"},
    "SE Asia": {"India/Pakistan", "Far East", "Australia"},
    "Far East": {"SE Asia"},
    "East/South Africa": {"Red Sea"},
    "Americas": set(),
    "Australia": {"SE Asia"},
}

ALIASES = {alias.strip(): region for region, names in REGIONS.items() for alias in names.split(",")}
LONGEST_FIRST = sorted(ALIASES, key=len, reverse=True)


def normalize(name):
    return " ".join(re.sub(r"[^\w.'\- ]", " ", str(name).lower().replace("(", " ").replace(")", " ")).split())


def region_of(name):
    """The trading region of a port or area name, or None when it is not in the table."""
    if not name:
        return None
    text = normalize(name)
    text = re.sub(r"^\d(?:-\d)?\s*s[bp]{1,3}p?\s+|^\d\s+", "", text)
    if text in ALIASES:
        return ALIASES[text]
    for alias in LONGEST_FIRST:
        if re.search(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", text):
            return ALIASES[alias]
    return None


def proximity(a, b):
    """3 same port, 2 same region, 1 neighbouring region, 0 unknown, -1 far apart."""
    if not a or not b:
        return 0
    if normalize(a) == normalize(b):
        return 3
    ra, rb = region_of(a), region_of(b)
    if not ra or not rb:
        return 0
    if ra == rb:
        return 2
    return 1 if rb in NEIGHBOURS.get(ra, set()) else -1
