import json
Q = []
def add(id, subject, type, question, must, *ev):
    Q.append({"id": id, "subject": subject, "type": type, "question": question, "must_include": must,
              "evidence": [{"file": f, "quote": q} for f, q in ev]})
L = "Law/"; S = "Software/"
A1, A2, A3 = L+"act-part-01-preliminary.md", L+"act-part-02-office-of-the-data-commissioner.md", L+"act-part-03-registration.md"
A4a, A4b = L+"act-part-04a-principles-and-rights.md", L+"act-part-04b-obligations-and-breach.md"
A6, A8, A1011 = L+"act-part-06-transfer-outside-kenya.md", L+"act-part-08-enforcement.md", L+"act-part-10-11-delegated-powers-and-miscellaneous.md"
G12, G3, G4 = L+"general-regs-part-01-02-rights-of-a-data-subject.md", L+"general-regs-part-03-commercial-use.md", L+"general-regs-part-04-obligations.md"
G6, G810, GS1 = L+"general-regs-part-06-breach-notification.md", L+"general-regs-part-08-10-impact-assessment-exemptions.md", L+"general-regs-schedule-1-forms.md"
C12, C3 = L+"complaints-regs-part-01-02-lodging-and-handling.md", L+"complaints-regs-part-03-enforcement-and-forms.md"
R1, RS = L+"registration-regs-regulations-01-18.md", L+"registration-regs-schedules-fees-and-thresholds.md"

# ---------------- LAW single
add("law-s-001", "law", "single", "Under Kenya's Data Protection Act, 2019, within how many hours of becoming aware of a personal data breach that poses a real risk of harm must a data controller notify the Data Commissioner?",
    [["seventy-two", "72"]], (A4b, "notify the Data Commissioner without delay, within seventy-two hours of becoming aware of such breach"))
add("law-s-002", "law", "single", "Under Kenya's Data Protection Act, 2019, when a data processor becomes aware of a personal data breach, within how many hours should it notify the data controller where reasonably practicable?",
    [["forty-eight", "48"]], (A4b, "the data processor shall notify the data controller without delay and where reasonably practicable, within forty-eight hours of becoming aware of such breach"))
add("law-s-003", "law", "single", "Under Kenya's Data Protection Act, 2019, how long is the Data Commissioner's term of office, and can it be renewed?",
    [["six years", "6 years", "six-year", "6-year"]], (A2, "The Data Commissioner shall be appointed for a single term of six years and shall not be eligible for a re-appointment."))
add("law-s-004", "law", "single", "Under Kenya's Data Protection Act, 2019, within how many days must a complaint made to the Data Commissioner be investigated and concluded?",
    [["ninety", "90"]], (A8, "A complaint made to the Data Commissioner shall be investigated and concluded within ninety days."))
add("law-s-005", "law", "single", "Under Kenya's Data Protection Act, 2019, what is the maximum administrative fine the Data Commissioner may impose in a penalty notice, both as a shilling amount and as a share of an undertaking's annual turnover?",
    [["five million", "5 million", "5,000,000"], ["one per centum", "1%", "1 %", "one per cent", "one percent", "1 per cent", "1 percent"]],
    (A8, "the maximum amount of the penalty that may be imposed by the Data Commissioner in a penalty notice is up to five million shillings, or in the case of an undertaking, up to one per centum of its annual turnover of the preceding financial year, whichever is lower"))
add("law-s-006", "law", "single", "Under the general penalty in Kenya's Data Protection Act, 2019, what is the maximum fine and the maximum prison term for an offence for which no specific penalty is provided?",
    [["three million", "3 million", "3,000,000"], ["ten years", "10 years"]],
    (A1011, "be liable to a fine not exceeding three million shillings or to an imprisonment term not exceeding ten years, or to both"))
add("law-s-007", "law", "single", "Under Kenya's Data Protection Act, 2019, how many days before the processing of data must data protection impact assessment reports be submitted?",
    [["sixty", "60"]], (A4a, "The data impact assessment reports shall be submitted sixty days prior to the processing of data."))
add("law-s-008", "law", "single", "Under Kenya's Data Protection Act, 2019, within what period must a data controller or data processor comply with a data portability request?",
    [["thirty days", "30 days"]], (A4b, "A data controller or data processor shall comply with data portability requests, at reasonable cost and within a period of thirty days."))
add("law-s-009", "law", "single", "Under Kenya's Data Protection Act, 2019, what is the shortest period an enforcement notice may give a person to implement the measures it specifies?",
    [["twenty-one days", "21 days"]], (A8, "specify a period which shall not be less than twenty-one days within which those measures shall be implemented"))
add("law-s-010", "law", "single", "Under Kenya's Data Protection Act, 2019, which body invites applications for the position of Data Commissioner when the office falls vacant, and within how many days of being notified of the vacancy must it do so?",
    [["Public Service Commission"], ["seven days", "7 days"]],
    (A2, "The Public Service Commission shall, within seven days of being notified of a vacancy under subsection (1), invite applications from persons who qualify for nomination and appointment for the position of the Data Commissioner."))
add("law-s-011", "law", "single", "Under Kenya's Data Protection Act, 2019, what is the minimum number of years of knowledge and relevant experience a person needs to qualify for appointment as Data Commissioner?",
    [["ten years", "10 years"]], (A2, "has knowledge and relevant experience of not less than ten years"))
add("law-s-012", "law", "single", "Under section 50 of Kenya's Data Protection Act, 2019, who may prescribe that certain processing shall only be effected through a server or data centre located in Kenya, and on what grounds?",
    [["Cabinet Secretary"], ["strategic interests", "protection of revenue"]],
    (A6, "The Cabinet Secretary may prescribe, based on grounds of strategic interests of the state or protection of revenue, certain nature of processing that shall only be effected through a server or a data centre located in Kenya."))
add("law-s-013", "law", "single", "Under Kenya's Data Protection (General) Regulations, 2021, within how many days must a data controller or data processor comply with a data subject's request to access their personal data?",
    [["seven days", "7 days"]], (G12, "comply with a request by a data subject to access their personal data within seven days"))
add("law-s-014", "law", "single", "Under Kenya's Data Protection (General) Regulations, 2021, where a data controller collects personal data indirectly, within how many days must it inform the data subject of the collection?",
    [["fourteen days", "14 days"]], (G12, "the data controller or data processor shall within fourteen days inform the data subject of the collection"))
add("law-s-015", "law", "single", "Under Kenya's Data Protection (General) Regulations, 2021, what is the maximum fine and the maximum prison term for a data controller convicted of using personal data for commercial purposes without the data subject's consent?",
    [["twenty thousand", "20,000"], ["six months", "6 months"]],
    (G3, "liable, on conviction, to a fine not exceeding twenty thousand shillings or to a term of imprisonment not exceeding six months, or to both fine and imprisonment"))
add("law-s-016", "law", "single", "Under Kenya's Data Protection (General) Regulations, 2021, which numbered form in the First Schedule is used to request rectification of personal data?",
    [["DPG 3", "DPG3"]], (G12, "A request for rectification may be made in Form DPG 3 set out in the First Schedule."))
add("law-s-017", "law", "single", "Under Kenya's Data Protection (General) Regulations, 2021, if a data controller submits a data protection impact assessment report to the Data Commissioner and receives no communication, after how many days may it commence processing with the report taken to have been approved?",
    [["sixty", "60"]], (G810, "does not receive any communication within sixty days of submission, may commence processing operations and the assessment report shall be taken to have been approved"))
add("law-s-018", "law", "single", "Under Kenya's Data Protection (General) Regulations, 2021, within how many days of a data subject's request must a data controller restrict the use or disclosure of personal data for facilitating direct marketing by a third party?",
    [["seven days", "7 days"]], (G3, "shall restrict use or disclosure of personal data for the purpose of facilitating direct marketing by a third party within seven days of the request"))
add("law-s-019", "law", "single", "Under Kenya's Data Protection (Complaints Handling Procedure and Enforcement) Regulations, 2021, which form does the Data Commissioner use to notify a respondent of an admitted complaint, and how many days does the respondent then have to act on it?",
    [["DPC 3", "DPC3"], ["twenty-one", "21 days", "21-day", "21 calendar days"]],
    (C12, "notify the respondent of the complaint lodged against him, in Form DPC 3 set out in the Schedule and shall require the respondent to within twenty-one days"))
add("law-s-020", "law", "single", "Under Kenya's Data Protection (Complaints Handling Procedure and Enforcement) Regulations, 2021, what is the maximum daily fine a penalty notice may impose for each breach until the breach is rectified?",
    [["ten thousand", "10,000"]], (C3, "A penalty notice may impose a daily fine of not more than ten thousand shillings for each breach identified until the breach is rectified."))
add("law-s-021", "law", "single", "Under Kenya's Data Protection (Complaints Handling Procedure and Enforcement) Regulations, 2021, to which court may a person appeal against an enforcement notice, and within how many days from the date of service?",
    [["High Court"], ["thirty days", "30 days"]],
    (C3, "a person may before the lapse of thirty days from the date of service of the enforcement notice, appeal to the High Court"))
add("law-s-022", "law", "single", "Under Kenya's Data Protection (Complaints Handling Procedure and Enforcement) Regulations, 2021, within what period from the date of decline may a complaint that was declined for admission be re-admitted if it raises new issues?",
    [["six months", "6 months"]], (C12, "the complaint may be re-admitted within six months from the date of decline, where the complaint raises new issues for determination under the Act"))
add("law-s-023", "law", "single", "Under Kenya's Data Protection (Registration of Data Controllers and Data Processors) Regulations, 2021, for how long is a certificate of registration valid from the date of issuance?",
    [["twenty-four months", "24 months", "two years", "2 years"]], (R1, "shall be valid for a period of twenty-four months from the date of issuance"))
add("law-s-024", "law", "single", "Under Kenya's Data Protection (Registration of Data Controllers and Data Processors) Regulations, 2021, below what annual turnover or revenue, and below what number of employees, is a data controller exempt from mandatory registration?",
    [["five million", "5 million", "5,000,000"], ["less than ten", "fewer than ten", "ten employees", "10 employees", "less than 10", "fewer than 10", "under ten", "under 10", "below ten", "below 10"]],
    (R1, "has an annual turnover of below five million shillings or annual revenue of below five million shillings; and"), (R1, "has less than ten employees"))
add("law-s-025", "law", "single", "Under the fee schedule of Kenya's Data Protection (Registration of Data Controllers and Data Processors) Regulations, 2021, what registration fee and what renewal fee, in Kenya shillings, does a large data controller (more than 99 employees) pay?",
    [["40,000", "40 000", "forty thousand"], ["25,000", "25 000", "twenty-five thousand"]],
    (RS, "Data controller/processor with more than 99 employees and an annual turnover/revenue of more than Kshs 50 Million | 40,000 | 25,000 |"))

# ---------------- LAW multi
add("law-m-001", "law", "multi", "In Kenya, a medium data controller (51 to 99 employees) holds a certificate of registration under the 2021 Registration Regulations. For how many months is the certificate valid, and what renewal fee in Kenya shillings does it pay?",
    [["twenty-four", "24"], ["9,000", "9 000", "nine thousand"]],
    (R1, "shall be valid for a period of twenty-four months from the date of issuance"),
    (RS, "between Kshs 5,000,001 and maximum of Kshs50,000,000 | 16,000 | 9,000 |"))
add("law-m-002", "law", "multi", "In Kenya, a private clinic with four employees and an annual turnover of two million shillings processes patient records to provide care. Is it excused from registering with the Data Commissioner under the 2021 Registration Regulations, and which Schedule of those Regulations decides the point?",
    [["Third Schedule"], ["not exempt", "not excused", "must register", "shall register", "required to register", "has to register", "does not apply", "shall not apply"]],
    (R1, "The exemption provided under subregulation (1) shall not apply to a data controller or data processor whose annual turnover is below five million shillings and processes personal data for the purposes specified under the Third Schedule."),
    (RS, "5. Health administration and provision of patient care."))
add("law-m-003", "law", "multi", "Under Kenyan data protection law, within how many hours must a data controller notify the Data Commissioner of a qualifying personal data breach under the 2019 Act, and which Schedule of the Data Protection (General) Regulations, 2021 lists the classes of personal data whose breach is notifiable?",
    [["seventy-two", "72"], ["Second Schedule"]],
    (A4b, "notify the Data Commissioner without delay, within seventy-two hours of becoming aware of such breach"),
    (G6, "any of the personal data or classes of personal data relating to the data subject set out in the Second Schedule"))
add("law-m-004", "law", "multi", "Under Kenya's Data Protection Act, 2019, how many days before processing must a data protection impact assessment report be submitted, and which Schedule of the Data Protection (General) Regulations, 2021 sets out the template for conducting the assessment?",
    [["sixty", "60"], ["Third Schedule"]],
    (A4a, "The data impact assessment reports shall be submitted sixty days prior to the processing of data."),
    (G810, "a data controller or data processor may conduct the assessment through a template set out in the Third Schedule"))
add("law-m-005", "law", "multi", "Under Kenyan data protection law, by what kind of instrument must a data controller engage a data processor under the Data Protection (General) Regulations, 2021, and within how many hours should that processor tell the controller about a personal data breach under the 2019 Act?",
    [["written contract"], ["forty-eight", "48"]],
    (G4, "a data controller shall engage a data processor, through a written contract"),
    (A4b, "the data processor shall notify the data controller without delay and where reasonably practicable, within forty-eight hours of becoming aware of such breach"))
add("law-m-006", "law", "multi", "Under Kenyan data protection law, what is the minimum number of days an enforcement notice must allow for implementing its measures under the 2019 Act, and within how many days of service may the notice be appealed under the 2021 Complaints Handling Procedure and Enforcement Regulations?",
    [["twenty-one", "21 days", "21-day", "21 calendar days"], ["thirty", "30"]],
    (A8, "specify a period which shall not be less than twenty-one days within which those measures shall be implemented"),
    (C3, "a person may before the lapse of thirty days from the date of service of the enforcement notice, appeal to the High Court"))
add("law-m-007", "law", "multi", "Under Kenyan data protection law, what is the maximum shilling amount of a penalty the Data Commissioner may impose in a penalty notice under the 2019 Act, and what maximum daily fine per breach may a penalty notice add under the 2021 Complaints Handling Procedure and Enforcement Regulations?",
    [["five million", "5 million", "5,000,000"], ["ten thousand", "10,000"]],
    (A8, "the maximum amount of the penalty that may be imposed by the Data Commissioner in a penalty notice is up to five million shillings"),
    (C3, "A penalty notice may impose a daily fine of not more than ten thousand shillings for each breach identified until the breach is rectified."))
add("law-m-008", "law", "multi", "Under Kenya's Data Protection Act, 2019, within how many days must a data portability request be complied with, and which numbered form in the Data Protection (General) Regulations, 2021 is used to make such a request?",
    [["thirty", "30"], ["DPG 4", "DPG4"]],
    (A4b, "A data controller or data processor shall comply with data portability requests, at reasonable cost and within a period of thirty days."),
    (G12, "A request for data portability may be made in Form DPG 4"))
add("law-m-009", "law", "multi", "In Kenya, a registered data controller fails to tell the Data Commissioner that its registered particulars have changed. Within how many days of the change was the written notification due under the 2021 Registration Regulations, and what is the maximum fine on conviction under the penalty of the 2019 Act that those Regulations apply?",
    [["fourteen", "14"], ["three million", "3 million", "3,000,000"]],
    (R1, "shall, within fourteen days of the occurrence of any changes in the particulars of a data controller or a data processor, notify the Data Commissioner in writing"),
    (R1, "commits an offence and shall, on conviction, be liable to the penalty specified under section 73 of the Act"),
    (A1011, "be liable to a fine not exceeding three million shillings or to an imprisonment term not exceeding ten years, or to both"))
add("law-m-010", "law", "multi", "In Kenya, compare two maximum fines: the fine under the Data Protection (General) Regulations, 2021 for using personal data for commercial purposes without consent, and the fine under the general penalty of the Data Protection Act, 2019. What are the two amounts?",
    [["twenty thousand", "20,000"], ["three million", "3 million", "3,000,000"]],
    (G3, "liable, on conviction, to a fine not exceeding twenty thousand shillings or to a term of imprisonment not exceeding six months, or to both fine and imprisonment"),
    (A1011, "be liable to a fine not exceeding three million shillings or to an imprisonment term not exceeding ten years, or to both"))
add("law-m-011", "law", "multi", "In Kenya, a company with 12 employees and an annual turnover of three million shillings applies to register as a data controller under the 2021 Registration Regulations. Which form does the application use, and what registration fee in Kenya shillings applies to it?",
    [["DPR1", "DPR 1"], ["4,000", "4 000", "four thousand"]],
    (R1, "be in Form DPR1 set out in the First Schedule"),
    (RS, "A data controller/ processor with between 1 and 50 employees and an annual turnover/revenue of amaximum of Kshs 5 Million | 4,000 | 2,000 |"))
add("law-m-012", "law", "multi", "In Kenya, once a complaint against a data controller is admitted, how many days does the respondent have to respond after being notified under the 2021 Complaints Handling Procedure and Enforcement Regulations, and within how many days overall must the complaint be investigated and concluded under the 2019 Act?",
    [["twenty-one", "21 days", "21-day", "21 calendar days"], ["ninety", "90"]],
    (C12, "shall require the respondent to within twenty-one days"),
    (A8, "A complaint made to the Data Commissioner shall be investigated and concluded within ninety days."))
add("law-m-013", "law", "multi", "In Kenya, a data controller is found to have given false information in its registration particulars. Under the 2021 Registration Regulations, which statute must guide the Data Commissioner before the certificate is cancelled, and what is the maximum fine on conviction under the general penalty of the Data Protection Act, 2019?",
    [["Fair Administrative Action"], ["three million", "3 million", "3,000,000"]],
    (R1, "be guided by the provisions of the Fair Administrative Actions Act, 2015 (Cap. 7J)"),
    (A3, "A data controller or data processor who knowingly supplies any false or misleading detail under subsection (1) commits an offence."),
    (A1011, "be liable to a fine not exceeding three million shillings or to an imprisonment term not exceeding ten years, or to both"))
add("law-m-014", "law", "multi", "Under Kenya's Data Protection Act, 2019, which office-holder keeps and maintains the register of data controllers and data processors, and how often must the list of registered controllers and processors be published on the official website under the 2021 Registration Regulations?",
    [["Data Commissioner"], ["thirty days", "30 days", "monthly", "every month"]],
    (A3, "The Data Commissioner shall keep and maintain a register of the registered data controllers and data processors."),
    (R1, "The Office shall, once every thirty days, publish on the official website a list of registered data controllers or data processors."))
add("law-m-015", "law", "multi", "Under section 50 of Kenya's Data Protection Act, 2019, who may prescribe processing that must take place in Kenya, and under the Data Protection (General) Regulations, 2021, what may a controller do instead of processing such data through a server and data centre located in Kenya?",
    [["Cabinet Secretary"], ["serving copy", "at least one"]],
    (A6, "The Cabinet Secretary may prescribe, based on grounds of strategic interests of the state or protection of revenue"),
    (G4, "store at least one serving copy of the concerned personal"))

# ---------------- SOFTWARE single
SQ1, SQ2 = S+"sqlite-releases-2026-01-to-07-3.51.2-to-3.53.4.md", S+"sqlite-releases-2026-10-3.54.0-and-3.54.1.md"
MC, MV, MM, MS = S+"mcp-2026-07-28-changelog.md", S+"mcp-2026-07-28-versioning.md", S+"mcp-2026-07-28-multi-round-trip-requests.md", S+"mcp-2026-07-28-subscriptions.md"
MD, MK, MT, MX = S+"mcp-2026-07-28-server-discover.md", S+"mcp-2026-07-28-caching.md", S+"mcp-2026-07-28-stdio-transport.md", S+"mcp-2026-07-28-deprecated-features.md"
P = lambda n: S + {1: "python-3.15-whatsnew-01-highlights-lazy-imports-frozendict-tachyon.md", 2: "python-3.15-whatsnew-02-new-features-continued.md",
                   3: "python-3.15-whatsnew-03-other-language-changes.md", 4: "python-3.15-whatsnew-04-improved-modules-a-to-m.md",
                   5: "python-3.15-whatsnew-05-improved-modules-o-to-z.md", 6: "python-3.15-whatsnew-06-optimizations-and-removed.md",
                   7: "python-3.15-whatsnew-07-deprecated.md", 8: "python-3.15-whatsnew-08-c-api-build-porting.md"}[n]
O14, O17, O20 = S+"ollama-releases-v0.14.0-to-v0.16.3.md", S+"ollama-releases-v0.17.0-to-v0.19.0.md", S+"ollama-releases-v0.20.0-to-v0.24.0.md"
O30, O32, O34, O40 = S+"ollama-releases-v0.30.0-to-v0.31.2.md", S+"ollama-releases-v0.32.0-to-v0.33.3.md", S+"ollama-releases-v0.34.0-to-v0.35.1.md", S+"ollama-releases-v0.40.0-to-v0.40.16.md"

add("sw-s-001", "software", "single", "What happened to SQLite release 3.52.0, dated 2026-03-06, and into which version were the features originally scheduled for it moved?",
    [["withdrawn"], ["3.53.0"]], (SQ1, "All of the features that were originally scheduled for the 3.52.0 release have been moved forward into version 3.53.0."))
add("sw-s-002", "software", "single", "In SQLite 3.53.0, released 2026-04-09, to how many significant digits are floating-point to text conversions rounded by default, and which sqlite3_db_config() option changes this?",
    [["17"], ["SQLITE_DBCONFIG_FP_DIGITS"]],
    (SQ1, "Rounding is now done by default to 17 significant digits, instead of 15, as was the case for all prior versions. The sqlite3_db_config(SQLITE_DBCONFIG_FP_DIGITS) API (item 6g above) can change this, if desired."))
add("sw-s-003", "software", "single", "Which new SQL statement in SQLite 3.53.0 (2026) rebuilds expression indexes, for example to repair stale ones?",
    [["REINDEX EXPRESSIONS"]], (SQ1, "The REINDEX EXPRESSIONS statement rebuilds expression indexes. (Useful to repair stale expression indexes.)"))
add("sw-s-004", "software", "single", "What is the name of the JavaScript/WASM VFS added in SQLite 3.53.0 (2026) that uses Web Locks for locking?",
    [["opfs-wl"]], (SQ1, "Add the \"opfs-wl\" VFS, functionally identical to the \"opfs\" VFS but using Web Locks for locking"))
add("sw-s-005", "software", "single", "SQLite 3.54.0, released 2026-10-09, dropped support for Windows XP and earlier. What is the oldest Windows version it now requires?",
    [["Vista"]], (SQ2, "SQLite for Windows now requires Windows Vista (circa 2007) or later."))
add("sw-s-006", "software", "single", "Which CLI dot-command, introduced in SQLite 3.54.0 (October 2026), replaces the separate sqlite3_analyzer utility program?",
    [[".diskused", "diskused"]], (SQ2, "Use the new diskused() extension to implement the \".diskused\" dot-command. The replaces the separate sqlite3_analyzer utility program, which is now deprecated."))
add("sw-s-007", "software", "single", "Which two conversions did SQLite 3.54.0 (October 2026) add to the built-in printf() and the format() SQL function for rendering JSON string literals?",
    [["%J", "%j"]], (SQ2, "Added the %J and %j conversions used to render JSON string literals to the built-in printf() and the format() SQL function."))
add("sw-s-008", "software", "single", "In the 2026-07-28 revision of the Model Context Protocol specification, which RPC must every server implement to advertise its supported protocol versions, capabilities and identity?",
    [["server/discover"]], (MC, "Add `server/discover`: servers MUST implement this RPC to advertise their supported protocol versions, capabilities, and identity."))
add("sw-s-009", "software", "single", "In the 2026-07-28 revision of the Model Context Protocol specification, which single method replaced the HTTP GET endpoint and resources/subscribe for server-to-client change notifications?",
    [["subscriptions/listen"]], (MS, "`subscriptions/listen` opens a long-lived notification stream from the server to the client."))
add("sw-s-010", "software", "single", "In the 2026-07-28 revision of the Model Context Protocol specification, to which JSON-RPC error code was UnsupportedProtocolVersion renumbered?",
    [["-32022", "32022"]], (MC, "`UnsupportedProtocolVersion` `-32004` → `-32022`"))
add("sw-s-011", "software", "single", "In the caching model of the 2026-07-28 Model Context Protocol specification, what are the names of the two fields that carry caching hints on cacheable results?",
    [["ttlMs"], ["cacheScope"]],
    (MK, "The <b>Time-to-live (TTL) Field</b>,`ttlMs`, is an integer value in milliseconds specifying how long the client MAY consider the result fresh."),
    (MK, "The <b>Cache Scope Field</b>,`cacheScope`, indicates the intended scope of the cached response, either `\"public\"` or `\"private\"`."))
add("sw-s-012", "software", "single", "Under the Multi Round-Trip Requests pattern of the 2026-07-28 Model Context Protocol specification, on which three client requests may a server respond with an InputRequiredResult?",
    [["tools/call"], ["resources/read"], ["prompts/get"]],
    (MM, "Servers **MAY** send `InputRequiredResult` responses on the following client requests:"),
    (MM, "Servers **MUST NOT** send `InputRequiredResult` responses on any other client requests."))
add("sw-s-013", "software", "single", "According to the deprecated features registry of the 2026-07-28 Model Context Protocol specification, the Roots, Sampling and Logging features may first be removed in the first revision released on or after what date?",
    [["2027-07-28"]], (MX, "First revision released on or after 2027-07-28"))
add("sw-s-014", "software", "single", "In the stdio transport of the 2026-07-28 Model Context Protocol specification, which notification must a client send to cancel an in-flight request?",
    [["notifications/cancelled"]], (MT, "To cancel an in-flight request, the client **MUST** send a `notifications/cancelled` notification referencing the request's ID."))
add("sw-s-015", "software", "single", "In the 2026-07-28 Model Context Protocol specification, which notification must a server send as the first message on a newly opened subscription stream?",
    [["subscriptions/acknowledged"]], (MS, "The server **MUST** send `notifications/subscriptions/acknowledged` as the first message"))
add("sw-s-016", "software", "single", "What maximum sampling rate, in Hz, does the Tachyon statistical sampling profiler added in Python 3.15 achieve?",
    [["1,000,000", "1000000", "1 000 000", "one million", "1 MHz", "1MHz"]], (P(1), "achieving sampling rates of up to 1,000,000 Hz"))
add("sw-s-017", "software", "single", "In Python 3.15, which environment variable enables lazy imports globally without modifying source code?",
    [["PYTHON_LAZY_IMPORTS"]], (P(1), "Python provides the `-X lazy_imports` command-line option and the `PYTHON_LAZY_IMPORTS` environment variable"))
add("sw-s-018", "software", "single", "Python 3.15 added a profiling package and deprecated the old profile module. In which Python version will the profile module be removed?",
    [["3.17"]], (P(1), "The `profile` module is deprecated and will be removed in Python 3.17."))
add("sw-s-019", "software", "single", "Which LLVM version does the experimental JIT compiler in Python 3.15 use for build-time stencil generation?",
    [["LLVM 21", "version 21", "21"]], (P(6), "The JIT compiler now uses LLVM 21 for build-time stencil generation."))
add("sw-s-020", "software", "single", "Which version of the TOML specification does the tomllib module support as of Python 3.15?",
    [["1.1.0", "TOML 1.1"]], (P(5), "The `tomllib` module now supports TOML 1.1.0."))
add("sw-s-021", "software", "single", "Python 3.15 added a configure option enabling huge page support for pymalloc arenas. To what size does the arena grow when it is enabled, and which environment variable must be set to 1 at runtime?",
    [["2 MiB", "2MiB", "2 MB", "2MB"], ["PYTHON_PYMALLOC_HUGEPAGES"]],
    (P(8), "When enabled, arena size increases to 2 MiB"), (P(8), "huge pages must be explicitly enabled by setting the `PYTHON_PYMALLOC_HUGEPAGES` environment variable to `1`"))
add("sw-s-022", "software", "single", "In Python 3.15.2, the ssl module began rejecting TLS certificate chains containing compromised intermediate CA certificates from which certificate authority?",
    [["eMudhra"]], (P(8), "The `ssl` module now rejects TLS certificate chains that contain one of a set of compromised eMudhra intermediate CA certificates."))
add("sw-s-023", "software", "single", "Since Ollama v0.15.5 (February 2026), what default context length does Ollama use on a system with 24 to 48 GiB of VRAM?",
    [["32,768", "32768", "32 768"]], (O14, "24-48 GiB VRAM: 32,768 context"))
add("sw-s-024", "software", "single", "Ollama v0.34.1 (September 2026) made the /api/tags endpoint much faster on large model libraries. From a cold time of 3.1 seconds, what cold time in milliseconds was measured afterwards?",
    [["294"]], (O34, "`/api/tags` is much faster on large model libraries (3.1 s → 294 ms cold in testing)"))
add("sw-s-025", "software", "single", "Ollama v0.32.15 (August 2026) began caching resolved model metadata between requests. In its benchmarks, to roughly how many milliseconds did time-to-first-token drop?",
    [["524"]], (O32, "cutting time-to-first-token by roughly half (TTFT dropped from ~995 ms to ~524 ms in benchmarks)"))

# ---------------- SOFTWARE multi
add("sw-m-001", "software", "multi", "Across SQLite 3.53.0 and 3.54.0 (both released in 2026), which three new options were added to the sqlite3_limit() interface?",
    [["SQLITE_LIMIT_PARSER_DEPTH"], ["SQLITE_LIMIT_SCHEMA"], ["SQLITE_LIMIT_TRIGGER_STEPS"]],
    (SQ1, "The SQLITE_LIMIT_PARSER_DEPTH option is added to sqlite3_limit()."),
    (SQ2, "Added SQLITE_LIMIT_SCHEMA and SQLITE_LIMIT_TRIGGER_STEPS to the sqlite3_limit() interface."))
add("sw-m-002", "software", "multi", "SQLite narrowed its Windows support twice in 2026. Which Windows platform did release 3.53.0 discontinue, and what is the oldest Windows version that release 3.54.0 requires?",
    [["Windows RT", "WindowsRT"], ["Vista"]],
    (SQ1, "Discontinue support for Windows RT."),
    (SQ2, "SQLite for Windows now requires Windows Vista (circa 2007) or later."))
add("sw-m-003", "software", "multi", "SQLite 3.53.0 (April 2026) added a library that the CLI uses to format query results, and SQLite 3.54.0 (October 2026) added two .mode options that control how integer and floating-point values are rendered with a printf-style format string. What is the library called, and what are the two options?",
    [["QRF", "Query Result Formatter"], ["--ifmt"], ["--fpfmt"]],
    (SQ1, "Add the Query Result Formatter (QRF) library for formatting the results of SQL queries for human readability on a fixed-pitch font screen."),
    (SQ2, "Enhance the .mode command with the new --ifmt option and --fpfmt option"))
add("sw-m-004", "software", "multi", "The 2026-07-28 revision of the Model Context Protocol removed logging/setLevel and deprecated the Logging feature. Which _meta key now sets the log level on each request, and on or after what date may the first revision that removes Logging be released?",
    [["io.modelcontextprotocol/logLevel", "logLevel"], ["2027-07-28"]],
    (MC, "Log level is now set per-request via `io.modelcontextprotocol/logLevel` in `_meta`"),
    (MX, "First revision released on or after 2027-07-28"))
add("sw-m-005", "software", "multi", "In the 2026-07-28 revision of the Model Context Protocol, which RPC must every server implement so that clients can query its versions and capabilities, and which field on that RPC's cacheable result tells the client how long the result stays fresh, and in what unit?",
    [["server/discover"], ["ttlMs"], ["millisecond"]],
    (MD, "`server/discover` lets a client query a server's supported protocol versions, capabilities, and identity before sending any other requests. Servers **MUST** implement it."),
    (MK, "The `ttlMs` field is a hint from the server indicating how long, in milliseconds, the client MAY consider the result fresh."))
add("sw-m-006", "software", "multi", "In the stdio transport of the 2026-07-28 Model Context Protocol specification, which _meta field must clients use to correlate notifications with the subscription they belong to, and what value does that field carry?",
    [["subscriptionId"], ["JSON-RPC ID", "JSON-RPC request ID", "request ID", "id of the"]],
    (MT, "Clients **MUST** correlate these using the `io.modelcontextprotocol/subscriptionId` field in `_meta`"),
    (MS, "The value is the JSON-RPC ID of the `subscriptions/listen` request."))
add("sw-m-007", "software", "multi", "In the 2026-07-28 revision of the Model Context Protocol, what resultType value marks an interim Multi Round-Trip Requests result, and which optional field of that result holds an opaque string that clients must not inspect or modify?",
    [["input_required"], ["requestState"]],
    (MC, "All results now carry a required `resultType` field: `\"complete\"` for ordinary results and `\"input_required\"` for"),
    (MM, "`requestState` _(optional)_: An opaque string meaningful only to the server. Clients **MUST NOT** inspect, parse, modify, or make any assumptions about its contents."))
add("sw-m-008", "software", "multi", "According to the 2026-07-28 Model Context Protocol specification, which protocol revision is the most recent one classed as legacy because it establishes a session with an initialize handshake, and since which protocol version has the HTTP+SSE transport been deprecated?",
    [["2025-11-25"], ["2025-03-26"]],
    (MV, "**Legacy**: protocol versions that establish a session with an `initialize` handshake (`2025-11-25` and earlier)."),
    (MC, "Reclassify the HTTP+SSE transport (deprecated since protocol version `2025-03-26`) as Deprecated under the feature lifecycle policy"))
add("sw-m-009", "software", "multi", "Python 3.15 builds CPython with frame pointers by default under PEP 831. Which two compiler flags does this use, and which configure option opts out?",
    [["-fno-omit-frame-pointer"], ["-mno-omit-leaf-frame-pointer"], ["--without-frame-pointers"]],
    (P(2), "This uses the compiler flags `-fno-omit-frame-pointer` and `-mno-omit-leaf-frame-pointer`"),
    (P(8), "Pass `--without-frame-pointers` to opt out."))
add("sw-m-010", "software", "multi", "Python 3.15.0 changed how the import system acquires per-module locks in order to fix a long-standing deadlock (gh-83065). In what order are the locks now acquired, and which later 3.15 release fixed the regression that this change introduced?",
    [["hierarchical", "parent packages before"], ["3.15.2"]],
    (P(3), "The import system now acquires per-module locks in hierarchical order (parent packages before their submodules)."),
    (P(8), "a regression introduced in 3.15.0 by the fix for gh-83065"))
add("sw-m-011", "software", "multi", "Which interpreter do the official Windows 64-bit binaries of Python 3.15 use, which compiler version made that possible, and what geometric-mean pyperformance speedup range is reported over the switch-case interpreter?",
    [["tail-calling", "tail calling"], ["MSVC 18", "Visual Studio 2026"], ["15-20%", "15–20%", "15 to 20", "15-20 %"]],
    (P(1), "The official Windows 64-bit binaries now use the tail-calling interpreter"),
    (P(8), "64-bit builds using Visual Studio 2026 (MSVC 18) may now use the new tail-calling interpreter. Results on Visual Studio 18.1.1 report between 15-20% speedup on the geometric mean of pyperformance on Windows x86-64 over the switch-case interpreter"))
add("sw-m-012", "software", "multi", "For the python -m http.server command-line interface in Python 3.15, which flag was removed together with CGIHTTPRequestHandler, and which new option customises the default Content-Type header for files with unknown extensions?",
    [["--cgi"], ["--content-type"]],
    (P(6), "Removed the `CGIHTTPRequestHandler` class and the `--cgi` flag from the python -m http.server command-line interface."),
    (P(4), "Added `default_content_type` and the `--content-type` command-line option to allow customizing the default `Content-Type` header for files with unknown extensions."))
add("sw-m-013", "software", "multi", "In which Ollama version of early 2026 did the `ollama launch` command for Claude Code, Codex, OpenCode and Droid first appear, and which later version added a flag to it that skips all prompts for non-interactive use? Name the flag too.",
    [["0.15.0"], ["0.18.0"], ["--yes"]],
    (O14, "New `ollama launch` command for Claude Code, Codex, OpenCode, and Droid"),
    (O17, "New `--yes` flag for `ollama launch` that skips all prompts, making it possible to run AI assistants and other tools in non-interactive environments"))
add("sw-m-014", "software", "multi", "Ollama Modelfiles gained two new instructions during 2026: one for declaring which version of Ollama a model needs, and one for explicitly declaring what a model can do. Which release introduced the first, and what is the second instruction called and which release introduced it?",
    [["0.14.0"], ["CAPABILITY"], ["0.35.1"]],
    (O14, "A new `REQUIRES` command for the `Modelfile` allows declaring which version of Ollama is required for the model"),
    (O34, "Modelfiles now support `CAPABILITY` declarations, so model creators can explicitly declare what a model can do."))
add("sw-m-015", "software", "multi", "Which Ollama release of 2026 first added experimental support for image generation models, and which later release temporarily removed experimental image generation?",
    [["0.14.0"], ["0.32.6"]],
    (O14, "New experimental support for image generation models, powered by MLX"),
    (O32, "Experimental image generation has been temporarily removed. Continue using 0.32.5 for image generation support"))

with open("../tasks/knowledge.jsonl", "w", encoding="utf-8") as f:
    for q in Q: f.write(json.dumps(q, ensure_ascii=False) + "\n")
print(len(Q), "questions written")
