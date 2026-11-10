import re, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from akn2md import chunks
RAW = "../_raw/law/kl/"; OUT = "../vault/Law/"
def load(fn, strip_header=False):
    s = open(RAW + fn).read()
    if strip_header: s = s.split("\n", 2)[2]
    return chunks(s)
def write(name, url, title, parts):
    body = "\n\n".join(p.strip() for p in parts if p.strip())
    fm = f"---\nsource: {url}\nfetched: 2026-11-10\ntitle: {title}\n---\n\n"
    open(OUT + name, "w").write(fm + body + "\n")
    print(f"{name:55s} {len(body):6d} chars")

A = "https://kenyalaw.org/akn/ke/act/2019/24/eng@2022-12-31"
c = [m for _, m in load("act.html")]
cover, pre, parts, sched = c[0], c[1], c[2:13], c[13:]
assert len(parts) == 11 and parts[10].startswith("## Part XI")
T = "Data Protection Act, 2019 (Cap. 411C)"
p4 = parts[3]; i = p4.index("### 37.")
p4a, p4b = p4[:i], "## Part IV – PRINCIPLES AND OBLIGATIONS OF PERSONAL DATA PROTECTION (continued)\n\n" + p4[i:]
write("act-part-01-preliminary.md", A, f"{T} — Part I: Preliminary (ss. 1–4)", [cover, pre, parts[0]])
write("act-part-02-office-of-the-data-commissioner.md", A, f"{T} — Part II: Establishment of the Office of Data Protection Commissioner (ss. 5–17)", [parts[1]])
write("act-part-03-registration.md", A, f"{T} — Part III: Registration of Data Controllers and Data Processors (ss. 18–24)", [parts[2]])
write("act-part-04a-principles-and-rights.md", A, f"{T} — Part IV: Principles and Obligations of Personal Data Protection (ss. 25–36)", [p4a])
write("act-part-04b-obligations-and-breach.md", A, f"{T} — Part IV continued: Principles and Obligations of Personal Data Protection (ss. 37–43)", [p4b])
write("act-part-05-sensitive-personal-data.md", A, f"{T} — Part V: Grounds for Processing of Sensitive Personal Data (ss. 44–47)", [parts[4]])
write("act-part-06-transfer-outside-kenya.md", A, f"{T} — Part VI: Transfer of Personal Data Outside Kenya (ss. 48–50)", [parts[5]])
write("act-part-07-exemptions.md", A, f"{T} — Part VII: Exemptions (ss. 51–55)", [parts[6]])
write("act-part-08-enforcement.md", A, f"{T} — Part VIII: Enforcement Provisions (ss. 56–66)", [parts[7]])
write("act-part-09-financial-provisions.md", A, f"{T} — Part IX: Financial Provisions (ss. 67–70)", [parts[8]])
write("act-part-10-11-delegated-powers-and-miscellaneous.md", A, f"{T} — Parts X and XI: Delegated Powers, Miscellaneous Provisions and Schedules (ss. 71–75)", [parts[9], parts[10]] + sched)

G = "https://kenyalaw.org/akn/ke/act/ln/2021/263/eng@2022-12-31"
c = [m for _, m in load("general.html")]
cover, P, S = c[0], c[1:11], c[11:]
assert len(P) == 10 and len(S) == 3
T = "Data Protection (General) Regulations, 2021 (Legal Notice 263 of 2021)"
write("general-regs-part-01-02-rights-of-a-data-subject.md", G, f"{T} — Parts I and II: Preliminary; Enabling the Rights of a Data Subject (regs. 1–13)", [cover, P[0], P[1]])
write("general-regs-part-03-commercial-use.md", G, f"{T} — Part III: Restrictions on the Commercial Use of Personal Data (regs. 14–18)", [P[2]])
write("general-regs-part-04-obligations.md", G, f"{T} — Part IV: Obligations of Data Controllers and Data Processors (regs. 19–26)", [P[3]])
write("general-regs-part-05-design-and-default.md", G, f"{T} — Part V: Elements to Implement Data Protection by Design or by Default (regs. 27–36)", [P[4]])
write("general-regs-part-06-breach-notification.md", G, f"{T} — Part VI: Notification of Personal Data Breaches (regs. 37–38) and Second Schedule", [P[5], S[1]])
write("general-regs-part-07-transfer-outside-kenya.md", G, f"{T} — Part VII: Transfer of Personal Data Outside Kenya (regs. 39–48)", [P[6]])
write("general-regs-part-08-10-impact-assessment-exemptions.md", G, f"{T} — Parts VIII to X: Data Protection Impact Assessment; Exemptions; General Provisions (regs. 49–58) and Third Schedule", [P[7], P[8], P[9], S[2]])
write("general-regs-schedule-1-forms.md", G, f"{T} — First Schedule: Forms for Data Subject Requests", [S[0]])

C = "https://kenyalaw.org/akn/ke/act/ln/2021/264/eng@2022-12-31"
c = [m for _, m in load("ln264.html", True)]
T = "Data Protection (Complaints Handling Procedure and Enforcement) Regulations, 2021 (Legal Notice 264 of 2021)"
assert len(c) == 5
write("complaints-regs-part-01-02-lodging-and-handling.md", C, f"{T} — Parts I and II: Preliminary; Procedure for Lodging, Admission and Response to Complaints (regs. 1–15)", c[0:3])
write("complaints-regs-part-03-enforcement-and-forms.md", C, f"{T} — Part III: Enforcement Provisions (regs. 16–22) and Schedule of Forms", c[3:])

R = "https://kenyalaw.org/akn/ke/act/ln/2021/265/eng@2022-12-31"
c = [m for _, m in load("ln265.html", True)]
T = "Data Protection (Registration of Data Controllers and Data Processors) Regulations, 2021 (Legal Notice 265 of 2021)"
write("registration-regs-regulations-01-18.md", R, f"{T} — Regulations 1–18", c[:-3])
write("registration-regs-schedules-fees-and-thresholds.md", R, f"{T} — Schedules: Registration Form, Fees and Thresholds for Mandatory Registration", c[-3:])
