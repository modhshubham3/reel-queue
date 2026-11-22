#!/usr/bin/env python3
"""Build week2/queue.csv (YouTube, 30 Shorts, 10 per channel, 2 per day per channel, 23-27 Nov 2026 IST)."""
import csv, pathlib
HERE = pathlib.Path(__file__).resolve().parent
IW = "Subscribe to Chai Dev | Interview Prep for one concept at a time. Instagram: @interview.chai\n\nAI-made explainer."
KW = "Roz ek nayi kahani. Subscribe karo: Kahaniyon Wali Raat. Instagram: @kahaniyon.wali.raat\n\nAI se bana animation."
GW = "How games commonly work, shown with a simple animation. It is not official and no Rockstar code is shown.\n\nFollow for how games really work. Instagram: @bawaalmoments\n\nAI-made explainer."
NET = "\n\nCode compiled and run on .NET 8 (C# 12)."
SQL = "\n\nBehaviour shown for SQL Server."
days = ["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27"]
def slots(times): return [(d, t) for d in days for t in times]
I = [  # id, file, title, description, tags, tail, hashtags
 ("i09", "i09_di", "Singleton vs Scoped vs Transient: say it in one line", "C# interview: what is the difference between singleton, scoped and transient in ASP.NET Core dependency injection? Chai stall analogy: one owner, one cup per visit, a new cup every time.", "C# interview,dotnet,dependency injection,ASP.NET Core,singleton scoped transient", "", "#CSharp #DotNet #Shorts #Interview #DependencyInjection"),
 ("i10", "i10_deltrunc", "DELETE vs TRUNCATE vs DROP: which one removes the table?", "SQL interview: DELETE picks rows, TRUNCATE empties the table, DROP removes it. The notebook analogy in 40 seconds.", "SQL interview,delete vs truncate vs drop,SQL Server,database", SQL, "#SQL #SQLServer #Shorts #Interview #Database"),
 ("i11", "i11_constro", "const vs readonly in C#: both 'cannot change', so what differs?", "C# interview: const is fixed at compile time, readonly is set once at runtime (per object). Real compiler errors CS0191 and CS0131 shown.", "C# interview,const vs readonly,dotnet,C# tricks", NET, "#CSharp #DotNet #Shorts #Interview #Coding"),
 ("i12", "i12_refout", "ref vs out in C#: both pass by reference, so what differs?", "C# interview: ref needs a value first, out must be assigned inside the method. The unassigned variable error CS0165 shown.", "C# interview,ref vs out,dotnet,C# tricks", NET, "#CSharp #DotNet #Shorts #Interview #Coding"),
 ("i13", "i13_boxing", "object o = 5; (long)o. Does it work? C# boxing trap", "C# interview: boxing and unboxing. Casting a boxed int straight to long throws InvalidCastException. Unbox to the exact type first.", "C# interview,boxing unboxing,InvalidCastException,dotnet", NET, "#CSharp #DotNet #Shorts #Interview #Boxing"),
 ("i14", "i14_linq", "LINQ quiz: filter first, then Add(4). How many match?", "C# quiz: LINQ is deferred. The query runs when you enumerate it, not when you write it. The recipe card analogy.", "C# interview,LINQ,deferred execution,dotnet,C# quiz", NET, "#CSharp #LINQ #DotNet #Shorts #Interview"),
 ("i15", "i15_finally", "return 1 inside try: does finally still run? C# interview", "C# interview: finally always runs, even after a return. Hotel key analogy and the real output order.", "C# interview,finally block,try catch finally,dotnet", NET, "#CSharp #DotNet #Shorts #Interview #Coding"),
 ("i16", "i16_nplus1", "Why is your API slow? The N+1 problem in 30 seconds", "Interview question: you loop over orders and load each customer. That is the N+1 problem: one query for the list, N for the details. Fix it with Include or a join.", "N+1 problem,Entity Framework,API performance,dotnet interview", "", "#DotNet #EntityFramework #Shorts #Interview #Performance"),
 ("i17", "i17_sqli", "One quote broke the login: SQL injection explained", "Security interview: building SQL with string plus lets the input become code. Use parameters so input stays data. The code shown is illustrative.", "SQL injection,security interview,parameterized query,SQL", "", "#SQL #Security #Shorts #Interview #SQLInjection"),
 ("i18", "i18_pkuk", "Primary key vs Unique key: the NULL trap (SQL Server)", "SQL interview: a table has one primary key and it never allows NULL. A unique key can exist many times and SQL Server allows one NULL.", "SQL interview,primary key vs unique key,SQL Server,database", SQL, "#SQL #SQLServer #Shorts #Interview #Database"),
]
K = [
 ("k09", "k09_birbal_murkh", "Akbar ka naam murkhon ki list mein kyun tha? | Birbal ki kahani", "Birbal ne murkhon ki list banayi aur sabse upar Akbar ka naam likha. Kyun? Akbar-Birbal ki lok-katha.", "Akbar Birbal,Birbal ki kahani,Hindi kahani,lok katha,moral story", "#Birbal #AkbarBirbal #Shorts #Kahani #HindiStories"),
 ("k10", "k10_birbal_kendra", "Dharti ka kendra kahan hai? Birbal ka jawab", "Akbar ne poochha: dharti ka kendra kahan hai? Birbal ne zameen mein ek loha gaad diya. Akbar-Birbal ki lok-katha.", "Akbar Birbal,Birbal ki kahani,Hindi kahani,lok katha,chatur Birbal", "#Birbal #AkbarBirbal #Shorts #Kahani #HindiStories"),
 ("k11", "k11_birbal_chor", "Chor ki daadhi mein tinka: Birbal ne chor kaise pakda?", "Chor ki daadhi mein tinka. Ye kahawat kahan se aayi? Akbar-Birbal ki lok-katha.", "Akbar Birbal,Birbal ki kahani,Hindi kahawat,lok katha,Hindi kahani", "#Birbal #AkbarBirbal #Shorts #Kahani #HindiStories"),
 ("k12", "k12_lakshman_rekha", "Lakshman Rekha ki kahani: Sita ne rekha kyun paar ki?", "Lakshman Rekha ka matlab kya hai? Katha ka ek prachalit roop.", "Lakshman Rekha,Ramayan,Ramayan ki kahani,Hindi kahani,Sita Lakshman", "#Ramayan #LakshmanRekha #Shorts #Kahani #HindiStories"),
 ("k13", "k13_ram_vachan", "Ram ne vanvaas bina shikayat ke kyun maana?", "Rajyabhishek ke ek din pehle Ram ko vanvaas mila. Unhone pita ke vachan ki wajah se use maan liya. Ramayan ka prasang.", "Ramayan,Ram vanvaas,Dasharath vachan,Hindi kahani,Ramayan ki kahani", "#Ramayan #Ram #Shorts #Kahani #HindiStories"),
 ("k14", "k14_arjun_moh", "Jab saamne apne hi hon: Arjun ka sawaal", "Kurukshetra mein Arjun ne dhanush rakh diya. Krishna ne unhe kya samjhaya? Mahabharat aur Gita ka prasang.", "Mahabharat,Arjun Krishna,Bhagavad Gita,Gita gyaan,Hindi kahani", "#Mahabharat #Gita #Shorts #Kahani #HindiStories"),
 ("k15", "k15_yudhi_kutta", "Yudhishthir swarg ke dwar par kutte ke liye ruk gaye", "Mahaprasthan mein Yudhishthir ke saath sirf ek kutta bacha. Swarg ke dwar par unhone kya chuna? Mahabharat ka prasang.", "Mahabharat,Yudhishthir,Mahaprasthan,Dharmraj,Hindi kahani", "#Mahabharat #Yudhishthir #Shorts #Kahani #HindiStories"),
 ("k16", "k16_lalchi_kutta", "Kutte ne roti kyun kho di? Tum bhi ye karte ho?", "Lalach ki lok-katha: kutte ne paani mein apni parchhai dekhi aur apni roti kho di.", "lalach ki kahani,moral story,Hindi kahani,lok katha,kutta aur roti", "#Kahani #MoralStory #Shorts #HindiStories #Lalach"),
 ("k17", "k17_sone_anda", "Sone ka anda dene wali murgi ka kya hua?", "Lalach ki ek aur lok-katha: sone ka anda dene wali murgi.", "sone ka anda,murgi ki kahani,moral story,Hindi kahani,lalach", "#Kahani #MoralStory #Shorts #HindiStories #Lalach"),
 ("k18", "k18_eklavya", "Eklavya ne angootha kyun de diya?", "Eklavya ne guru dakshina mein apna angootha de diya. Is kahani par log alag alag sochte hain. Aap kya sochte ho? Mahabharat ka prasang.", "Mahabharat,Eklavya,Dronacharya,guru dakshina,Hindi kahani", "#Mahabharat #Eklavya #Shorts #Kahani #HindiStories"),
]
G = [
 ("g06", "g06_stream", "How GTA-style open worlds load a city with no loading screen", "How can a huge open world run with no loading screen? The map is cut into squares, and only the ones near you are loaded.", "GTA 6,open world,game development,how games work,loading screen"),
 ("g07", "g07_traffic", "Why game traffic never runs out (hundreds of cars)", "Where do all the cars in an open-world city come from? Roads are a graph, and only cars near you are simulated.", "GTA 6,game traffic AI,game development,how games work,open world"),
 ("g08", "g08_collision", "Why a 300 km/h car can't clip through a wall", "Tunneling: when a fast object skips a thin wall between two physics steps. The fix is to sweep the whole path.", "GTA 6,game physics,collision detection,tunneling,game development"),
 ("g09", "g09_culling", "How games skip drawing most of the city", "Frustum and occlusion culling in a simple top-down demo: only what the camera can see gets drawn.", "GTA 6,culling,game rendering,game development,how games work"),
 ("g10", "g10_path", "How NPCs find their way: pathfinding in 40 seconds", "Breadth-first search vs A star on a grid, with a new wall and a replan. The numbers shown are from this demo grid only.", "GTA 6,pathfinding,A star,NPC AI,game development"),
 ("g11", "g11_frame", "16.7 ms: the budget every game frame lives inside", "At 60 FPS every frame gets about 16.7 milliseconds. Go over and you feel it as a stutter. The split shown is an example, not real numbers.", "GTA 6,frame time,60 fps,game performance,game development"),
 ("g12", "g12_lod", "Why far cars look simpler: level of detail (LOD)", "Level of detail: near objects use the detailed model, far ones a cheaper copy. Swap too early and you see the pop.", "GTA 6,level of detail,LOD,game graphics,game development"),
 ("g13", "g13_crowd", "1000 people, 5 characters: how game crowds are made", "A crowd is a few base models remixed with colour, size and a random walk offset.", "GTA 6,game crowd,NPC,game development,how games work"),
 ("g14", "g14_sun", "In a game, the sun is just a number", "Time of day is one number that sets the sun angle, the sky colour and every shadow.", "GTA 6,day night cycle,game lighting,game development,how games work"),
 ("g15", "g15_engine", "Why a game engine sound is never one recording", "Engine audio in games is usually a few loops, pitch-shifted and crossfaded by RPM.", "GTA 6,game audio,engine sound,game development,how games work"),
]
rows = []
for (a, b), r in zip(slots(["12:30", "17:30"]), I):
    rows.append([r[0], "interview", f"videos/{r[1]}.mp4", r[2], f"{r[3]}{r[5]}\n\n{IW}\n\n{r[6]}", r[4], f"{a} {b}", "no", "yes"])
for (a, b), r in zip(slots(["07:30", "19:00"]), K):
    rows.append([r[0], "kahani", f"videos/{r[1]}.mp4", r[2], f"{r[3]}\n\nKatha / lok-katha ka ek prachalit roop.\n\n{KW}\n\n{r[5]}", r[4], f"{a} {b}", "no", "yes"])
for (a, b), r in zip(slots(["15:00", "21:00"]), G):
    rows.append([r[0], "gta", f"videos/{r[1]}.mp4", r[2], f"{r[3]}\n\n{GW}\n\n#Shorts #GTA6 #GameDev #HowGamesWork #GameDesign", r[4], f"{a} {b}", "no", "yes"])
with open(HERE / "queue.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["id", "channel", "file", "title", "description", "tags", "publish_at", "made_for_kids", "synthetic"]); w.writerows(rows)
print(len(rows), "rows; longest title", max(len(r[3]) for r in rows))
