import { formatarTamanho } from "./formatacao";

test("formata o tamanho em B, KB e MB com vírgula decimal", () => {
  expect(formatarTamanho(0)).toBe("0 B");
  expect(formatarTamanho(512)).toBe("512 B");
  expect(formatarTamanho(1536)).toBe("1,5 KB");
  expect(formatarTamanho(2_411_724)).toBe("2,3 MB");
});
