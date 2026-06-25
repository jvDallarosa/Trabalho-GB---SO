import threading
import random
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

PAGE_SIZE        = 8 * 1024           # 8 KB
MAIN_MEMORY_SIZE = 64 * 1024          # 64 KB
VIRTUAL_MEM_SIZE = 1 * 1024 * 1024   # 1 MB
NUM_FRAMES       = MAIN_MEMORY_SIZE // PAGE_SIZE   # 8 frames
NUM_PAGES        = VIRTUAL_MEM_SIZE  // PAGE_SIZE  # 128 paginas

@dataclass
class PageTableEntry:
    page_number: int
    frame_number: Optional[int] = None
    present: bool = False
    last_used: float = 0.0


@dataclass
class Frame:
    frame_number: int
    free: bool = True
    owner_pid: Optional[int] = None
    owner_page: Optional[int] = None
    data: str = ""

class MainMemory:
    def __init__(self):
        self.frames = [Frame(i) for i in range(NUM_FRAMES)]

    def get_free_frame(self) -> Optional[int]:
        for f in self.frames:
            if f.free:
                return f.frame_number
        return None

    def load_page(self, frame_num: int, pid: int, page: int, data: str):
        f = self.frames[frame_num]
        f.free       = False
        f.owner_pid  = pid
        f.owner_page = page
        f.data       = data

    def evict_frame(self, frame_num: int):
        f = self.frames[frame_num]
        evicted = (f.owner_pid, f.owner_page)
        f.free       = True
        f.owner_pid  = None
        f.owner_page = None
        f.data       = ""
        return evicted

    def display(self):
        print()
        print("--------------------------------------------------")
        print("  MEMORIA PRINCIPAL  ({} frames x {} KB)".format(NUM_FRAMES, PAGE_SIZE // 1024))
        print("--------------------------------------------------")
        print("  {:>5}  {:>5}  {:>4}  {:>6}  {}".format("Frame", "Livre", "PID", "Pagina", "Conteudo"))
        print("  " + "-" * 48)
        for f in self.frames:
            livre  = "Sim" if f.free else "Nao"
            pid    = str(f.owner_pid)  if not f.free else "-"
            page   = str(f.owner_page) if not f.free else "-"
            data   = f.data[:20] + "..." if f.data and len(f.data) > 20 else (f.data or "-")
            print("  {:>5}  {:>5}  {:>4}  {:>6}  {}".format(f.frame_number, livre, pid, page, data))
        print()

class LightProcess:

    def __init__(self, pid: int, size_bytes: int):
        self.pid       = pid
        self.size      = size_bytes
        self.num_pages = max(1, (size_bytes + PAGE_SIZE - 1) // PAGE_SIZE)

        # Conteudo simulado para cada pagina
        self.virtual_data = {
            p: "PID{}_PG{:03d}_{}".format(
                pid, p,
                "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=16))
            )
            for p in range(self.num_pages)
        }

        # Tabela de paginas
        self.page_table = {
            p: PageTableEntry(p) for p in range(self.num_pages)
        }

    def virtual_to_page_offset(self, virtual_addr: int):
        page   = virtual_addr // PAGE_SIZE
        offset = virtual_addr %  PAGE_SIZE
        return page, offset

    def display_page_table(self):
        print()
        print("  Tabela de Paginas -- PID {}".format(self.pid))
        print("  {:>6}  {:>8}  {:>5}".format("Pagina", "Presente", "Frame"))
        print("  " + "-" * 25)
        for p, e in self.page_table.items():
            presente = "Sim" if e.present else "Nao"
            frame    = str(e.frame_number) if e.present else "-"
            print("  {:>6}  {:>8}  {:>5}".format(p, presente, frame))
        print()

class MMU:

    def __init__(self, main_memory: MainMemory):
        self.memory    = main_memory
        self.lock      = threading.Lock()
        self.lru_order = OrderedDict()
        self.stats     = {"hits": 0, "faults": 0}

    def _lru_touch(self, frame_num: int):
        if frame_num in self.lru_order:
            self.lru_order.move_to_end(frame_num)
        else:
            self.lru_order[frame_num] = frame_num

    def _lru_evict_frame(self) -> int:
        frame_num, _ = self.lru_order.popitem(last=False)
        return frame_num

    def translate(self, process: LightProcess, virtual_addr: int, processes: dict):
        page_num, offset = process.virtual_to_page_offset(virtual_addr)

        if page_num >= process.num_pages:
            print("  [ERRO] Endereco {} fora do espaco do PID {}".format(virtual_addr, process.pid))
            return None

        with self.lock:
            entry = process.page_table[page_num]

            print()
            print("=" * 55)
            print("  PID {} | Endereco Virtual: 0x{:06X}  (Pagina {}, Offset {})".format(
                process.pid, virtual_addr, page_num, offset))

            # HIT
            if entry.present:
                self.stats["hits"] += 1
                frame_num = entry.frame_number
                phys_addr = frame_num * PAGE_SIZE + offset
                entry.last_used = time.time()
                self._lru_touch(frame_num)

                print("  [HIT]  Pagina {} -> Frame {}  |  Endereco Fisico: 0x{:06X}".format(
                    page_num, frame_num, phys_addr))
                print("  Conteudo: {}".format(process.virtual_data[page_num]))
                return process.virtual_data[page_num]

            # PAGE FAULT
            else:
                self.stats["faults"] += 1
                print("  [FALTA DE PAGINA]  Pagina {} nao esta na memoria principal!".format(page_num))

                free_frame = self.memory.get_free_frame()

                if free_frame is not None:
                    print("  -> Frame livre encontrado: Frame {}".format(free_frame))
                    self._load_page(process, page_num, free_frame)

                else:
                    victim_frame = self._lru_evict_frame()
                    victim_f     = self.memory.frames[victim_frame]
                    victim_pid   = victim_f.owner_pid
                    victim_page  = victim_f.owner_page

                    print("  -> Sem frames livres. Substituindo via LRU: Frame {} (PID {}, Pagina {})".format(
                        victim_frame, victim_pid, victim_page))

                    if victim_pid in processes:
                        vp = processes[victim_pid]
                        if victim_page in vp.page_table:
                            vp.page_table[victim_page].present      = False
                            vp.page_table[victim_page].frame_number = None

                    self.memory.evict_frame(victim_frame)
                    self._load_page(process, page_num, victim_frame)
                    free_frame = victim_frame

                phys_addr = free_frame * PAGE_SIZE + offset
                print("  Endereco Fisico apos carga: 0x{:06X}".format(phys_addr))
                print("  Conteudo: {}".format(process.virtual_data[page_num]))
                return process.virtual_data[page_num]

    def _load_page(self, process: LightProcess, page_num: int, frame_num: int):
        data = process.virtual_data[page_num]
        self.memory.load_page(frame_num, process.pid, page_num, data)

        entry = process.page_table[page_num]
        entry.present      = True
        entry.frame_number = frame_num
        entry.last_used    = time.time()
        self._lru_touch(frame_num)
        print("  -> Pagina {} carregada no Frame {}".format(page_num, frame_num))

class VirtualMemorySimulator:

    def __init__(self):
        self.memory    = MainMemory()
        self.mmu       = MMU(self.memory)
        self.processes = {}

    def add_process(self, pid: int, size_bytes: int):
        size_bytes = max(1, min(size_bytes, VIRTUAL_MEM_SIZE))
        p = LightProcess(pid, size_bytes)
        self.processes[pid] = p
        print("  Processo PID {} criado: {} bytes -> {} pagina(s)".format(
            pid, size_bytes, p.num_pages))
        return p

    def _worker(self, process: LightProcess, accesses: list):
        for vaddr in accesses:
            self.mmu.translate(process, vaddr, self.processes)
            time.sleep(random.uniform(0.05, 0.15))

    def run(self, num_accesses: int = 15):
        print()
        print("=" * 55)
        print("  SIMULADOR DE MEMORIA VIRTUAL")
        print("=" * 55)
        print("  Memoria Principal : {} KB  ({} frames de {} KB)".format(
            MAIN_MEMORY_SIZE // 1024, NUM_FRAMES, PAGE_SIZE // 1024))
        print("  Memoria Virtual   : {} KB ({} paginas de {} KB)".format(
            VIRTUAL_MEM_SIZE // 1024, NUM_PAGES, PAGE_SIZE // 1024))
        print("  Substituicao      : LRU")
        print()

        p1 = self.add_process(1, random.randint(PAGE_SIZE,      VIRTUAL_MEM_SIZE // 2))
        p2 = self.add_process(2, random.randint(PAGE_SIZE * 2,  VIRTUAL_MEM_SIZE))

        def rand_addrs(proc, n):
            return [random.randint(0, proc.size - 1) for _ in range(n)]

        addrs1 = rand_addrs(p1, num_accesses)
        addrs2 = rand_addrs(p2, num_accesses)

        print()
        print("  Iniciando {} acessos por processo em threads paralelas...".format(num_accesses))

        t1 = threading.Thread(target=self._worker, args=(p1, addrs1))
        t2 = threading.Thread(target=self._worker, args=(p2, addrs2))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Relatorio final
        print()
        print("=" * 55)
        print("  RELATORIO FINAL")
        print("=" * 55)
        print("  Page hits   : {}".format(self.mmu.stats["hits"]))
        print("  Page faults : {}".format(self.mmu.stats["faults"]))
        total = self.mmu.stats["hits"] + self.mmu.stats["faults"]
        if total:
            rate = self.mmu.stats["hits"] / total * 100
            print("  Hit rate    : {:.1f}%".format(rate))

        self.memory.display()

        for p in self.processes.values():
            p.display_page_table()


if __name__ == "__main__":
    random.seed(42)
    sim = VirtualMemorySimulator()
    sim.run(num_accesses=15)