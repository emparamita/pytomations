#!/usr/bin/env python
"""Oracle (ODBC) vs .dat validation -> colour-coded xlsx report. All config via .env.

Usage (from workspace root):
  python validate_data.py [--env .env] [--init-env] [--check-deps] [--install-deps]
Exit codes: 0 match | 1 differences | 2 error
"""
import argparse, datetime as dt, glob, importlib, logging, os, re, shutil, subprocess, sys
from decimal import Decimal, InvalidOperation

PKGS = {"pandas": "pandas", "numpy": "numpy", "openpyxl": "openpyxl",
        "pyodbc": "pyodbc", "dotenv": "python-dotenv"}
log = logging.getLogger("validate")

# ---------------------------------------------------------------- bootstrap
def missing_deps():
    out = []
    for mod, pkg in PKGS.items():
        try:
            importlib.import_module(mod)
        except ImportError:
            out.append(pkg)
    return out

def install_deps():
    miss = missing_deps()
    if not miss:
        return
    conda = shutil.which("conda")
    if conda:
        subprocess.call([conda, "install", "-y", "-c", "conda-forge"] + miss)
        miss = missing_deps()
    if miss:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + miss)

def init_env(dest=".env.example"):
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.example")
    shutil.copyfile(src, dest)
    print("Created", dest)

# ---------------------------------------------------------------- config
def b(v, d=False):
    return d if v in (None, "") else str(v).strip().lower() in ("1", "true", "yes", "y")

def load_config(env_path):
    from dotenv import load_dotenv
    if not os.path.isfile(env_path):
        raise FileNotFoundError(f"Env file not found: {env_path} (copy .env.example to .env)")
    load_dotenv(env_path, override=True)
    g = lambda k, d="": os.getenv(k, d)
    sep = (g("DAT_SEPARATOR") or "|").replace("\\t", "\t")
    cs = lambda k: [x.strip() for x in g(k).split(",") if x.strip()]
    cfg = dict(
        connection_mode=(g("ORACLE_CONNECTION_MODE", "odbc").strip().lower() or "odbc"),
        dbapi_dsn=g("ORACLE_DBAPI_DSN").strip(),
        dsn=g("ORACLE_ODBC_DSN").strip(), user=g("ORACLE_USER").strip(), pwd=g("ORACLE_PASSWORD"),
        conn_str=g("ORACLE_ODBC_CONN_STR").strip(), timeout=int(g("ORACLE_LOGIN_TIMEOUT", "30") or 30),
        query=g("ORACLE_QUERY").strip(), table=g("ORACLE_TABLE").strip(), order_by=g("ORACLE_ORDER_BY").strip(),
        dat_path=g("DAT_FILE_PATH").strip(), sep=sep, encoding=g("DAT_ENCODING", "utf-8-sig").strip() or "utf-8-sig",
        has_header=b(g("DAT_HAS_HEADER"), True), ignore=[c.upper() for c in cs("DAT_IGNORE_COLUMNS")],
        keys=cs("KEY_COLUMNS"), trim=b(g("TRIM_WHITESPACE"), True), ci=b(g("CASE_INSENSITIVE"), False),
        null_tokens=set(cs("NULL_TOKENS")),
        date_formats=cs("DATE_FORMATS") or ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"],
        report_dir=g("REPORT_DIR", "reports").strip() or "reports",
        prefix=g("REPORT_FILE_PREFIX", "data_validation").strip() or "data_validation",
    )
    if not cfg["dat_path"]:
        raise ValueError("DAT_FILE_PATH is required")
    if not (cfg["query"] or cfg["table"]):
        raise ValueError("Set ORACLE_QUERY or ORACLE_TABLE")
    if cfg["connection_mode"] not in {"odbc", "oracledb"}:
        raise ValueError("ORACLE_CONNECTION_MODE must be 'odbc' or 'oracledb'")
    if cfg["connection_mode"] == "oracledb" and not (cfg["dbapi_dsn"] and cfg["user"] and cfg["pwd"]):
        raise ValueError("oracledb mode requires ORACLE_DBAPI_DSN, ORACLE_USER, and ORACLE_PASSWORD")
    if cfg["connection_mode"] == "odbc" and not (cfg["conn_str"] or (cfg["dsn"] and cfg["user"])):
        raise ValueError("Set ORACLE_ODBC_DSN + ORACLE_USER + ORACLE_PASSWORD (or ORACLE_ODBC_CONN_STR)")
    return cfg

# ---------------------------------------------------------------- sources
def fetch_db(cfg):
    import pandas as pd
    if cfg["query"]:
        sql = cfg["query"].rstrip().rstrip(";")
    else:
        if not re.fullmatch(r"[A-Za-z0-9_.$#\"]+", cfg["table"]):
            raise ValueError("Invalid ORACLE_TABLE")
        sql = f"SELECT * FROM {cfg['table']}" + (f" ORDER BY {cfg['order_by']}" if cfg["order_by"] else "")
    if not re.match(r"^\s*(select|with)\b", sql, re.I):
        raise ValueError("Only SELECT/WITH queries are allowed")
    if not cfg["keys"] and not re.search(r"order\s+by", sql, re.I):
        log.warning("Position matching without ORDER BY: row order from Oracle is not guaranteed")
    if cfg["connection_mode"] == "oracledb":
        try:
            import oracledb
        except ImportError as exc:
            raise RuntimeError(
                "Install python-oracledb with `python -m pip install -e '.[oracle-dbapi]'`"
            ) from exc
        conn = oracledb.connect(user=cfg["user"], password=cfg["pwd"], dsn=cfg["dbapi_dsn"])
    else:
        import pyodbc
        esc = "{" + cfg["pwd"].replace("}", "}}") + "}"
        if cfg["conn_str"]:
            cs = cfg["conn_str"].replace("%USER%", cfg["user"]).replace("%PASSWORD%", cfg["pwd"])
        else:
            cs = f"DSN={cfg['dsn']};UID={cfg['user']};PWD={esc}"
        conn = pyodbc.connect(cs, timeout=cfg["timeout"])
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        types = [d[1] for d in cur.description]
        rows = [tuple(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return pd.DataFrame(rows, columns=cols, dtype=object), types

def resolve_dat_path(p):
    today = dt.date.today()
    p = p.replace("{YYYYMMDD}", today.strftime("%Y%m%d")).replace("{YYYY-MM-DD}", today.isoformat())
    if any(ch in p for ch in "*?["):
        hits = glob.glob(p)
        if not hits:
            raise FileNotFoundError(f"No file matches {p}")
        return max(hits, key=os.path.getmtime)
    if not os.path.isfile(p):
        raise FileNotFoundError(f"DAT file not found: {p}")
    return p

def read_dat(path, cfg, ncols_db):
    import pandas as pd
    kw = dict(sep=cfg["sep"], dtype=str, keep_default_na=False, na_filter=False, encoding=cfg["encoding"],
              engine="python" if len(cfg["sep"]) > 1 else "c", skip_blank_lines=True)
    df = pd.read_csv(path, header=0 if cfg["has_header"] else None, **kw)
    if cfg["has_header"]:
        df.columns = [str(c).strip() for c in df.columns]
    elif df.shape[1] == ncols_db + 1:
        df = df.iloc[:, 1:]          # header-less file with leading exported_date
    return df

# ---------------------------------------------------------------- normalization
def kind_of(t):
    type_name = getattr(t, "name", "").upper()
    if type_name in {"DB_TYPE_DATE", "DB_TYPE_TIMESTAMP", "DB_TYPE_TIMESTAMP_TZ", "DB_TYPE_TIMESTAMP_LTZ"}:
        return "date"
    if type_name in {"DB_TYPE_NUMBER", "DB_TYPE_BINARY_FLOAT", "DB_TYPE_BINARY_DOUBLE"}:
        return "num"
    try:
        if issubclass(t, dt.date):
            return "date"
        if issubclass(t, (int, float, Decimal)) and not issubclass(t, bool):
            return "num"
    except TypeError:
        pass
    return "str"

def _iso(ts):
    ts = ts.replace(microsecond=0) if ts.microsecond == 0 else ts
    return ts.date().isoformat() if (ts.hour, ts.minute, ts.second, ts.microsecond) == (0, 0, 0, 0) else ts.isoformat(" ")

def norm_value(v, kind, cfg):
    if v is None or (isinstance(v, float) and v != v):
        return ""
    if isinstance(v, dt.datetime):
        return _iso(v)
    if isinstance(v, dt.date):
        return v.isoformat()
    s = v if isinstance(v, str) else str(v)
    if cfg["trim"]:
        s = s.strip()
    if s in cfg["null_tokens"] or s == "":
        return ""
    if kind == "num":
        try:
            d = Decimal(s)
            if d.is_finite():
                out = format(d.normalize(), "f")
                return "0" if out in ("-0", "") else out
        except InvalidOperation:
            pass
    elif kind == "date":
        for f in cfg["date_formats"]:
            try:
                return _iso(dt.datetime.strptime(s, f))
            except ValueError:
                continue
    return s.upper() if cfg["ci"] else s

def normalize_frame(df, kinds, cfg):
    import pandas as pd
    columns = {
        c: df[c].map(lambda v, k=k: norm_value(v, k, cfg))
        for c, k in zip(df.columns, kinds)
    }
    return pd.DataFrame(columns, index=df.index)

def make_keys(nd, key_cols):
    import pandas as pd
    if len(nd) == 0:
        return pd.Series([], dtype=object)
    k = nd[key_cols[0]]
    for c in key_cols[1:]:
        k = k + "\x1f" + nd[c]
    return k + "\x1e" + k.groupby(k).cumcount().astype(str)

# ---------------------------------------------------------------- compare
def compare(db, dat_cmp, kinds, cfg):
    """db / dat_cmp share identical columns. Returns statuses + diff column lists (positional)."""
    import numpy as np
    cols = list(db.columns)
    nd_db, nd_dat = normalize_frame(db, kinds, cfg), normalize_frame(dat_cmp, kinds, cfg)
    n_db, n_dat = len(db), len(dat_cmp)
    s_db, s_dat = ["MATCH"] * n_db, ["MATCH"] * n_dat
    d_db, d_dat = [[] for _ in range(n_db)], [[] for _ in range(n_dat)]
    stats = {"db_rows": n_db, "dat_rows": n_dat, "duplicate_keys_db": 0, "duplicate_keys_dat": 0}

    if cfg["keys"]:
        up = {c.upper(): c for c in cols}
        kc = []
        for k in cfg["keys"]:
            if k.upper() not in up:
                raise ValueError(f"KEY column '{k}' not found in DB columns")
            kc.append(up[k.upper()])
        k_db, k_dat = make_keys(nd_db, kc), make_keys(nd_dat, kc)
        stats["duplicate_keys_db"] = int(k_db.str.rsplit("\x1e", n=1).str[0].duplicated().sum()) if n_db else 0
        stats["duplicate_keys_dat"] = int(k_dat.str.rsplit("\x1e", n=1).str[0].duplicated().sum()) if n_dat else 0
        a, bb = nd_db.set_axis(k_db.values), nd_dat.set_axis(k_dat.values)
        common = a.index[a.index.isin(bb.index)]
        pos_db = dict(zip(a.index, range(n_db)))
        pos_dat = dict(zip(bb.index, range(n_dat)))
        for k in a.index[~a.index.isin(bb.index)]:
            s_db[pos_db[k]] = "MISSING_IN_DAT"
        for k in bb.index[~bb.index.isin(a.index)]:
            s_dat[pos_dat[k]] = "EXTRA_IN_DAT"
        pairs = [(pos_db[k], pos_dat[k]) for k in common]
        va, vb = a.loc[common].values, bb.loc[common].values
    else:
        n = min(n_db, n_dat)
        for i in range(n, n_db):
            s_db[i] = "MISSING_IN_DAT"
        for i in range(n, n_dat):
            s_dat[i] = "EXTRA_IN_DAT"
        pairs = [(i, i) for i in range(n)]
        va, vb = nd_db.iloc[:n].values, nd_dat.iloc[:n].values

    if len(pairs):
        diff = va != vb
        for r in np.nonzero(diff.any(axis=1))[0]:
            i, j = pairs[r]
            names = [cols[c] for c in np.nonzero(diff[r])[0]]
            s_db[i] = s_dat[j] = "MISMATCH"
            d_db[i], d_dat[j] = names, names
    return s_db, s_dat, d_db, d_dat, stats

# ---------------------------------------------------------------- report
COLORS = {"MISMATCH": "FFC7CE", "MISSING_IN_DAT": "F8CBAD", "EXTRA_IN_DAT": "FFFF99", "NOT_COMPARED": "D9D9D9"}

def _clean(df):
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE as RE
    df = df.copy()
    for c in df.columns:
        df[c] = df[c].map(lambda v: RE.sub("", v) if isinstance(v, str) else v)
    return df

def _style_sheet(ws, statuses, diffs, colpos, ncols):
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    F = lambda **k: Font(name="Arial", size=10, **k)
    hdr = PatternFill("solid", fgColor="1F3864")
    for c in ws[1]:
        c.font = F(bold=True, color="FFFFFF")
        c.fill = hdr
    for c in (ws.cell(1, ncols + 1), ws.cell(1, ncols + 2)):
        c.fill = PatternFill("solid", fgColor="7F7F7F")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for idx in range(1, ncols + 3):
        mx = 10
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 200), min_col=idx, max_col=idx):
            v = row[0].value
            mx = max(mx, min(len(str(v)) if v is not None else 0, 50))
        ws.column_dimensions[get_column_letter(idx)].width = mx + 2
    cell_fill = PatternFill("solid", fgColor="FF9999")
    for i, st in enumerate(statuses):
        if st == "MATCH":
            continue
        fill = PatternFill("solid", fgColor=COLORS[st])
        for c in range(1, ncols + 3):
            ws.cell(i + 2, c).fill = fill
        for name in diffs[i]:
            cell = ws.cell(i + 2, colpos[name] + 1)
            cell.fill, cell.font = cell_fill, F(bold=True, color="9C0006")

def write_report(path, dat_raw, db_raw, s_dat, s_db, d_dat, d_db, dat_colpos, db_colpos, summary, notes):
    import pandas as pd
    from openpyxl.styles import Font, PatternFill
    if max(len(dat_raw), len(db_raw)) > 1_048_574:
        raise ValueError("Data exceeds Excel row limit")
    t1, t2 = dat_raw.copy(), db_raw.copy()
    t1["Validation_Status"], t1["Diff_Columns"] = s_dat, [", ".join(x) for x in d_dat]
    t2["Validation_Status"], t2["Diff_Columns"] = s_db, [", ".join(x) for x in d_db]
    rows = [("Metric", "Value")] + summary + [("", "")] + [("Note", n) for n in notes]
    sm = pd.DataFrame(rows[1:], columns=rows[0])
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        _clean(t1).to_excel(xw, sheet_name="DAT_Data", index=False)
        _clean(t2).to_excel(xw, sheet_name="DB_Data", index=False)
        sm.to_excel(xw, sheet_name="Summary", index=False)
        wb = xw.book
        _style_sheet(wb["DAT_Data"], s_dat, d_dat, dat_colpos, dat_raw.shape[1])
        _style_sheet(wb["DB_Data"], s_db, d_db, db_colpos, db_raw.shape[1])
        ws = wb["Summary"]
        for c in ws[1]:
            c.font, c.fill = Font(name="Arial", bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F3864")
        ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 28, 90
        r = ws.max_row + 2
        ws.cell(r, 1, "Legend").font = Font(name="Arial", bold=True)
        legend = [("MISMATCH", "Row exists in both; row red, differing cells dark red"),
                  ("MISSING_IN_DAT", "Row in DB but not in DAT (orange)"),
                  ("EXTRA_IN_DAT", "Row in DAT but not in DB (yellow)"),
                  ("NOT_COMPARED", "Structural column issue (grey)")]
        for k, (name, txt) in enumerate(legend, 1):
            ws.cell(r + k, 1, name).fill = PatternFill("solid", fgColor=COLORS[name])
            ws.cell(r + k, 2, txt)
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.font = Font(name="Arial", size=10, bold=c.font.bold)

# ---------------------------------------------------------------- main flow
def run(cfg, db, types, dat_raw, out_dir):
    notes, cols = [], list(db.columns)
    db_u = [c.upper() for c in cols]
    dat_names = [str(c).strip() for c in dat_raw.columns]
    # drop ignored columns (only if not DB columns)
    keep = [i for i, n in enumerate(dat_names) if not (n.upper() in cfg["ignore"] and n.upper() not in db_u)]
    for i in range(len(dat_names)):
        if i not in keep:
            notes.append(f"Ignored DAT column: {dat_names[i]}")
    kept_u = [dat_names[i].upper() for i in keep]
    structural = False
    if len(set(kept_u)) != len(kept_u):
        notes.append("DAT has duplicate column names"); structural = True
    miss, extra = [c for c in db_u if c not in kept_u], [c for c in kept_u if c not in db_u]
    if miss: notes.append("Columns missing in DAT: " + ", ".join(miss)); structural = True
    if extra: notes.append("Unexpected columns in DAT: " + ", ".join(extra)); structural = True
    if not structural and kept_u != db_u:
        notes.append("Column order differs between DB and DAT (DAT reordered for comparison)")

    kinds = [kind_of(t) for t in types]
    nd, ne = len(dat_raw), len(db)
    if structural:
        s_db, s_dat = ["NOT_COMPARED"] * ne, ["NOT_COMPARED"] * nd
        d_db, d_dat = [[] for _ in range(ne)], [[] for _ in range(nd)]
        stats = {"db_rows": ne, "dat_rows": nd}
        dat_colpos = {}
    else:
        pos_by_u = {dat_names[i].upper(): i for i in keep}
        dat_colpos = {c: pos_by_u[c.upper()] for c in cols}
        cmp = dat_raw.iloc[:, [dat_colpos[c] for c in cols]].copy()
        cmp.columns = cols
        s_db, s_dat, d_db, d_dat, stats = compare(db, cmp, kinds, cfg)
    db_colpos = {c: i for i, c in enumerate(cols)}

    cnt = lambda s, k: sum(1 for x in s if x == k)
    mism = cnt(s_db, "MISMATCH")
    summary = [("Run time", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
               ("Match mode", ("Key: " + ", ".join(cfg["keys"])) if cfg["keys"] else "Row position"),
               ("DB rows", stats["db_rows"]), ("DAT rows", stats["dat_rows"]),
               ("Matching rows", cnt(s_db, "MATCH")), ("Mismatched rows", mism),
               ("Rows in DB missing from DAT", cnt(s_db, "MISSING_IN_DAT")),
               ("Extra rows in DAT", cnt(s_dat, "EXTRA_IN_DAT")),
               ("Duplicate keys (DB / DAT)", f"{stats.get('duplicate_keys_db', 0)} / {stats.get('duplicate_keys_dat', 0)}"),
               ("Result", "FAIL" if (structural or mism or "MISSING_IN_DAT" in s_db or "EXTRA_IN_DAT" in s_dat) else "PASS")]
    path = os.path.join(out_dir, f"{cfg['prefix']}_{dt.datetime.now():%H%M%S}.xlsx")
    write_report(path, dat_raw, db, s_dat, s_db, d_dat, d_db, dat_colpos, db_colpos, summary, notes)
    return path, summary[-1][1] == "PASS", summary

def main():
    ap = argparse.ArgumentParser(description="Validate Oracle data against a .dat export")
    ap.add_argument("--env", default=".env")
    ap.add_argument("--init-env", action="store_true", help="write .env.example to the current folder")
    ap.add_argument("--check-deps", action="store_true")
    ap.add_argument("--install-deps", action="store_true")
    a = ap.parse_args()
    if a.init_env:
        return init_env() or 0
    if a.install_deps:
        install_deps()
    m = missing_deps()
    if a.check_deps or m:
        print("Missing packages: " + ", ".join(m) if m else "All dependencies available")
        return 2 if m else 0
    out_dir = None
    try:
        cfg = load_config(a.env)
        out_dir = os.path.join(cfg["report_dir"], dt.date.today().isoformat())
        os.makedirs(out_dir, exist_ok=True)
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                            handlers=[logging.StreamHandler(), logging.FileHandler(os.path.join(out_dir, "validation.log"), encoding="utf-8")])
        log.info("Fetching Oracle data")
        db, types = fetch_db(cfg)
        path_dat = resolve_dat_path(cfg["dat_path"])
        log.info("Reading %s", path_dat)
        dat = read_dat(path_dat, cfg, db.shape[1])
        path, ok, summary = run(cfg, db, types, dat, out_dir)
        for k, v in summary:
            log.info("%s: %s", k, v)
        log.info("Report: %s", path)
        return 0 if ok else 1
    except Exception as e:   # never log secrets
        msg = f"ERROR: {type(e).__name__}: {e}"
        log.error(msg)
        return 2

if __name__ == "__main__":
    sys.exit(main())
