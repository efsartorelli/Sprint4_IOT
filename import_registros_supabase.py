# import_registros_supabase.py
import os, csv, sys, datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()  # carrega variáveis do arquivo .env da pasta atual


try:
    import psycopg
except ImportError:
    print("Instale as dependências: pip install 'psycopg[binary]'")
    sys.exit(1)

PG_DSN = os.getenv("PG_DSN")
CSV_PATH = os.getenv("CSV_PATH", "registro.csv")

if not PG_DSN:
    print("Defina a variável de ambiente PG_DSN com sua connection string do Supabase.")
    sys.exit(1)

TZ = ZoneInfo("America/Sao_Paulo")

def parse_bool(v: str) -> bool | None:
    if v is None:
        return None
    s = v.strip().lower()
    return True if s in ("sim", "s", "1", "true", "verdadeiro") else False

def parse_dt(date_str: str, time_str: str) -> datetime.datetime:
    """
    Converte 'dd/mm/yyyy' + 'HH:MM[:SS]' para datetime timezone-aware America/Sao_Paulo
    """
    date_str = date_str.strip()
    time_str = time_str.strip()
    fmts = ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"]
    last_err = None
    for fmt in fmts:
        try:
            dt_naive = datetime.datetime.strptime(f"{date_str} {time_str}", fmt)
            return dt_naive.replace(tzinfo=TZ)
        except Exception as e:
            last_err = e
    raise last_err

DDL = """
CREATE TABLE IF NOT EXISTS access_events (
  id            bigserial PRIMARY KEY,
  pessoa        text        NOT NULL,
  status        text        NOT NULL CHECK (status IN ('Aprovado','Negado')),
  primeira_vez  boolean,
  event_time    timestamptz NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_access_events_event_time ON access_events (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_access_events_pessoa_time ON access_events (pessoa, event_time DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uniq_access_key
  ON access_events (pessoa, event_time, status, primeira_vez);
"""

INSERT_SQL = """
INSERT INTO access_events (pessoa, status, primeira_vez, event_time)
VALUES (%s, %s, %s, %s)
ON CONFLICT (pessoa, event_time, status, primeira_vez) DO NOTHING;
"""

def read_rows(csv_path: str):
    """
    Lê CSV sem cabeçalho:
    col0=data, col1=hora, col2=pessoa, col3=status, col4=primeira_vez, col5=id(ignorar)
    Ignora linhas em branco.
    """
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f, delimiter=",")
        for i, row in enumerate(r, start=1):
            # Ignora linhas vazias
            if not row or all((c or "").strip() == "" for c in row):
                continue

            # tolera colunas a mais; usa as 6 primeiras se existirem
            # estrutura esperada: 6 colunas
            if len(row) < 5:
                print(f"[linha {i}] ignorada: colunas insuficientes: {row}")
                continue

            # unpack tolerante
            date_str = row[0]
            time_str = row[1] if len(row) > 1 else ""
            pessoa   = row[2] if len(row) > 2 else ""
            status   = row[3] if len(row) > 3 else ""
            primvez  = row[4] if len(row) > 4 else None
            # id_csv   = row[5] if len(row) > 5 else None  # ignorado

            pessoa = (pessoa or "").strip()
            status_norm = (status or "").strip().capitalize()
            if status_norm not in ("Aprovado", "Negado"):
                # tenta normalizar melhor (ex.: "negado", "NEGADO", "aprovado")
                sn = status_norm.lower()
                if "aprov" in sn:
                    status_norm = "Aprovado"
                elif "neg" in sn:
                    status_norm = "Negado"
                else:
                    # se vier algo diferente, mantém texto original sem travar
                    status_norm = (status or "").strip()

            try:
                dt = parse_dt(date_str, time_str)  # tz-aware America/Sao_Paulo
            except Exception as e:
                print(f"[linha {i}] erro em data/hora '{date_str} {time_str}': {e}")
                continue

            yield (pessoa, status_norm, parse_bool(primvez), dt)

def main():
    rows = list(read_rows(CSV_PATH))
    if not rows:
        print("Nenhuma linha válida encontrada no CSV.")
        return

    print(f"Linhas válidas no CSV: {len(rows)}")
    with psycopg.connect(PG_DSN) as con:
        with con.cursor() as cur:
            # garante DDL
            for stmt in filter(None, DDL.split(";")):
                s = stmt.strip()
                if s:
                    cur.execute(s + ";")

            # insere em lote
            cur.executemany(INSERT_SQL, rows)

        con.commit()
    print("Importação concluída sem erros (duplicatas ignoradas).")

if __name__ == "__main__":
    main()
