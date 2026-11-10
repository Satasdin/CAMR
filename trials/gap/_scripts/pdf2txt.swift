import Foundation
import PDFKit
for p in CommandLine.arguments.dropFirst() {
    guard let d = PDFDocument(url: URL(fileURLWithPath: p)) else { print("fail", p); continue }
    var s = ""
    for i in 0..<d.pageCount { s += "\n<<<PAGE \(i+1)>>>\n" + (d.page(at: i)?.string ?? "") }
    let out = String(p.dropLast(4)) + ".txt"
    try! s.write(toFile: out, atomically: true, encoding: .utf8)
    print(p, d.pageCount, "pages", s.count, "chars")
}
