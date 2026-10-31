import csv, io, json, sys

def check(text):
    issues=[]
    try:
        rows=list(csv.reader(io.StringIO(text.lstrip("\ufeff")),strict=True))
    except csv.Error as exc:
        return {"issues":[{"kind":"invalid_csv","detail":str(exc)}],"data_rows":0}
    if not rows:
        return {"issues":[{"kind":"empty_file"}],"data_rows":0}
    headers=rows[0]
    if any(not h.strip() for h in headers): issues.append({"kind":"blank_header"})
    normalized=[h.strip().casefold() for h in headers]
    if len(set(normalized))!=len(normalized): issues.append({"kind":"duplicate_header"})
    for line,row in enumerate(rows[1:],2):
        if len(row)!=len(headers): issues.append({"kind":"column_count","record":line,"expected":len(headers),"actual":len(row)})
    return {"issues":issues,"data_rows":len(rows)-1,"columns":len(headers)}

if __name__=="__main__":
    with open(sys.argv[1],encoding="utf-8",newline="") as source: result=check(source.read())
    print(json.dumps(result,indent=2))
    sys.exit(1 if result["issues"] else 0)
