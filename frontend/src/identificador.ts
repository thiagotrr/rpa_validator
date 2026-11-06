let sequencia = 0;

/** Identificador local para itens de lista (não precisa ser único fora desta sessão da tela). */
export const novoId = (): string => `item-${++sequencia}`;
