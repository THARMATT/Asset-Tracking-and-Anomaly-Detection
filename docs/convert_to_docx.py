import os
import zipfile
import xml.sax.saxutils as saxutils

def make_docx(output_path, markdown_path):
    with open(markdown_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Base XML parts for a valid .docx
    content_types_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

    rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    doc_rels_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
        <w:color w:val="222222"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="160" w:line="240" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
</w:styles>'''

    # Parse markdown lines into Word paragraphs/tables
    body_xml = []
    in_code_block = False
    code_lines = []

    def esc(text):
        return saxutils.escape(text)

    def p(text, bold=False, size=22, color="222222", heading_level=None, align=None):
        jc_elem = f'<w:jc w:val="{align}"/>' if align else ''
        b_elem = '<w:b/>' if bold else ''
        spacing = '<w:spacing w:before="120" w:after="80"/>'
        if heading_level == 1:
            spacing = '<w:spacing w:before="360" w:after="140"/>'
        elif heading_level == 2:
            spacing = '<w:spacing w:before="240" w:after="100"/>'

        return f'''<w:p>
  <w:pPr>
    {jc_elem}
    {spacing}
  </w:pPr>
  <w:r>
    <w:rPr>
      {b_elem}
      <w:sz w:val="{size}"/>
      <w:szCs w:val="{size}"/>
      <w:color w:val="{color}"/>
    </w:rPr>
    <w:t xml:space="preserve">{esc(text)}</w:t>
  </w:r>
</w:p>'''

    def code_p(text):
        return f'''<w:p>
  <w:pPr>
    <w:spacing w:before="20" w:after="20"/>
    <w:pBdr>
      <w:left w:val="single" w:sz="12" w:space="4" w:color="3B82F6"/>
    </w:pBdr>
    <w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/>
  </w:pPr>
  <w:r>
    <w:rPr>
      <w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>
      <w:sz w:val="18"/>
      <w:color w:val="1E293B"/>
    </w:rPr>
    <w:t xml:space="preserve">{esc(text)}</w:t>
  </w:r>
</w:p>'''

    table_buffer = []

    def flush_table(buf):
        if not buf:
            return ""
        # parse rows
        rows = [r.strip() for r in buf if not r.strip().startswith('|:')]
        xml = ['''<w:tbl>
  <w:tblPr>
    <w:tblW w:w="0" w:type="auto"/>
    <w:tblBorders>
      <w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>
      <w:left w:val="none"/>
      <w:bottom w:val="single" w:sz="8" w:space="0" w:color="94A3B8"/>
      <w:right w:val="none"/>
      <w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
      <w:insideV w:val="none"/>
    </w:tblBorders>
  </w:tblPr>''']
        for r_idx, row in enumerate(rows):
            cols = [c.strip() for c in row.split('|')[1:-1]]
            is_header = (r_idx == 0)
            shd = '<w:shd w:val="clear" w:color="auto" w:fill="E2E8F0"/>' if is_header else ''
            xml.append('  <w:tr>')
            for c in cols:
                xml.append(f'''    <w:tc>
      <w:tcPr>
        {shd}
        <w:tcMar>
          <w:top w:w="120" w:type="dxa"/>
          <w:left w:w="160" w:type="dxa"/>
          <w:bottom w:w="120" w:type="dxa"/>
          <w:right w:w="160" w:type="dxa"/>
        </w:tcMar>
      </w:tcPr>
      <w:p>
        <w:pPr><w:spacing w:before="40" w:after="40"/></w:pPr>
        <w:r>
          <w:rPr>
            {'<w:b/>' if is_header else ''}
            <w:sz w:val="20"/>
            <w:color w:val="0F172A"/>
          </w:rPr>
          <w:t xml:space="preserve">{esc(c)}</w:t>
        </w:r>
      </w:p>
    </w:tc>''')
            xml.append('  </w:tr>')
        xml.append('</w:tbl>')
        xml.append('<w:p><w:pPr><w:spacing w:before="60" w:after="60"/></w:pPr></w:p>')
        return "\n".join(xml)

    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\r\n')
        
        # Handle code blocks
        if line.startswith('```'):
            if in_code_block:
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            body_xml.append(code_p(line))
            i += 1
            continue

        # Handle Markdown tables
        if line.startswith('|'):
            table_buffer.append(line)
            i += 1
            continue
        elif table_buffer:
            body_xml.append(flush_table(table_buffer))
            table_buffer = []

        # Handle headings
        if line.startswith('# '):
            body_xml.append(p(line[2:].strip(), bold=True, size=36, color="1E3A8A", heading_level=1, align="center"))
        elif line.startswith('## '):
            body_xml.append(p(line[3:].strip(), bold=True, size=28, color="1E40AF", heading_level=2))
        elif line.startswith('### '):
            body_xml.append(p(line[4:].strip(), bold=True, size=24, color="2563EB", heading_level=3))
        elif line.startswith('#### '):
            body_xml.append(p(line[5:].strip(), bold=True, size=22, color="334155", heading_level=4))
        elif line.startswith('- ') or line.startswith('* '):
            body_xml.append(p("•  " + line[2:].strip(), size=22, color="334155"))
        elif line.strip() == '---':
            # Separator
            body_xml.append('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="CBD5E1"/></w:pBdr><w:spacing w:before="120" w:after="160"/></w:pPr></w:p>')
        elif line.strip():
            # Paragraph
            # Basic cleanup of bold markers if any
            clean_text = line.replace('**', '').replace('`', '')
            body_xml.append(p(clean_text, size=22, color="334155"))
        else:
            # Empty line
            pass

        i += 1

    if table_buffer:
        body_xml.append(flush_table(table_buffer))

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {"".join(body_xml)}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
    </w:sectPr>
  </w:body>
</w:document>'''

    # Write as a zip file with .docx extension
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as docx:
        docx.writestr('[Content_Types].xml', content_types_xml)
        docx.writestr('_rels/.rels', rels_xml)
        docx.writestr('word/_rels/document.xml.rels', doc_rels_xml)
        docx.writestr('word/document.xml', document_xml)
        docx.writestr('word/styles.xml', styles_xml)

    print(f"Successfully generated DOCX at: {output_path}")

if __name__ == "__main__":
    md_file = r"C:\Users\NIGAM SHARMA\OneDrive\Desktop\Asset  Tracking system\docs\lab_manual_project_report.md"
    docx_file = r"C:\Users\NIGAM SHARMA\OneDrive\Desktop\Asset  Tracking system\docs\lab_manual_project_report.docx"
    make_docx(docx_file, md_file)
