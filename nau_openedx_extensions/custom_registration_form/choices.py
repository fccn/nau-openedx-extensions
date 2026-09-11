"""
Controlled lists for the NAU extended user profile.

Values are short stable codes so that rewording a label never becomes a data
migration. Labels are Portuguese literals and are deliberately not wrapped in
``gettext``: these values are exported in ``student_profile_info``, which runs
inside a Celery task where the active language is not guaranteed, and the
reports have to read in Portuguese.
"""

# Employment situation ("Situação profissional").
#
# LEGACY_PUBLIC_SERVICE_CONTRACT is the pre-existing "Public service contract"
# option. It was split into the ten "Função Pública" entries below, so there is
# no single value to migrate it to. It is kept as a selectable choice so that
# existing answers keep displaying and validating; users pick a specific entry
# the next time they edit their profile.
LEGACY_PUBLIC_SERVICE_CONTRACT = "public_service_contract"

EMPLOYMENT_SITUATION_CHOICES = [
    ("student", "Estudante"),
    ("unemployed", "Desempregado"),
    ("self_employed", "Trabalhador independente/empresário"),
    ("private_institution_contract", "Contrato por conta de outrem em instituição privada"),
    ("public_senior_manager_1", "Trabalhador da Função Pública: Dirigente Superior de 1.º grau"),
    ("public_senior_manager_2", "Trabalhador da Função Pública: Dirigente Superior 2.º grau"),
    ("public_middle_manager_1", "Trabalhador da Função Pública: Dirigente Intermédio 1.º grau"),
    ("public_middle_manager_2", "Trabalhador da Função Pública: Dirigente Intermédio 2.º grau"),
    ("public_senior_technician", "Trabalhador da Função Pública: Técnico/a Superior"),
    ("public_technical_assistant", "Trabalhador da Função Pública: Assistente Técnico/a"),
    ("public_operational_assistant", "Trabalhador da Função Pública: Assistente Operacional"),
    ("public_special_career", "Trabalhador da Função Pública: Carreira Especial ou com designação específica"),
    ("public_other_career", "Trabalhador da Função Pública: Outra carreira"),
    ("public_other_manager", "Trabalhador da Função Pública: Outro cargo dirigente ou equiparado"),
    ("other", "Outro"),
    (LEGACY_PUBLIC_SERVICE_CONTRACT, "Contrato com instituição pública (opção anterior)"),
]

# Maps the values stored by the previous choice list to the new codes.
# Applied by migration 0015. "Public service contract" is intentionally absent:
# see LEGACY_PUBLIC_SERVICE_CONTRACT above.
EMPLOYMENT_SITUATION_LEGACY_MAP = {
    "Student": "student",
    "Unemployed": "unemployed",
    "Self employed entrepreneur": "self_employed",
    "Private institution contract": "private_institution_contract",
    "Other": "other",
    "Public service contract": LEGACY_PUBLIC_SERVICE_CONTRACT,
}

# NUTS II — NUTS III, as a single merged field.
NUTS_CHOICES = [
    ("alentejo_alentejo_central", "Alentejo — Alentejo Central"),
    ("alentejo_alentejo_litoral", "Alentejo — Alentejo Litoral"),
    ("alentejo_alto_alentejo", "Alentejo — Alto Alentejo"),
    ("alentejo_baixo_alentejo", "Alentejo — Baixo Alentejo"),
    ("algarve_algarve", "Algarve — Algarve"),
    ("centro_beira_baixa", "Centro — Beira Baixa"),
    ("centro_beiras_e_serra_da_estrela", "Centro — Beiras e Serra da Estrela"),
    ("centro_medio_tejo", "Centro — Médio Tejo"),
    ("centro_regiao_de_aveiro", "Centro — Região de Aveiro"),
    ("centro_regiao_de_coimbra", "Centro — Região de Coimbra"),
    ("centro_regiao_de_leiria", "Centro — Região de Leiria"),
    ("centro_viseu_dao_lafoes", "Centro — Viseu Dão-Lafões"),
    ("grande_lisboa", "Grande Lisboa — Grande Lisboa"),
    ("norte_alto_minho", "Norte — Alto Minho"),
    ("norte_alto_tamega_e_barroso", "Norte — Alto Tâmega e Barroso"),
    ("norte_area_metropolitana_do_porto", "Norte — Área Metropolitana do Porto"),
    ("norte_ave", "Norte — Ave"),
    ("norte_cavado", "Norte — Cávado"),
    ("norte_douro", "Norte — Douro"),
    ("norte_tamega_e_sousa", "Norte — Tâmega e Sousa"),
    ("norte_terras_de_tras_os_montes", "Norte — Terras de Trás-os-Montes"),
    ("oeste_vale_tejo_leziria_do_tejo", "Oeste e Vale do Tejo — Lezíria do Tejo"),
    ("oeste_vale_tejo_oeste", "Oeste e Vale do Tejo — Oeste"),
    ("peninsula_de_setubal", "Península de Setúbal — Península de Setúbal"),
    ("regiao_autonoma_da_madeira", "Região Autónoma da Madeira — Região Autónoma da Madeira"),
    ("regiao_autonoma_dos_acores", "Região Autónoma dos Açores — Região Autónoma dos Açores"),
    ("nao_aplicavel_fora_de_portugal", "Não aplicável — Residente fora de Portugal"),
]

# CAE4, economic activity sector.
CAE4_CHOICES = [
    ("primary_agriculture", "Setor primário: Agricultura, floresta e pesca"),
    ("primary_extractive", "Setor primário: Indústrias extrativas"),
    ("secondary_manufacturing", "Setor secundário: Indústrias transformadoras"),
    (
        "secondary_energy",
        "Setor secundário: Produção e distribuição de eletricidade, gás, vapor e ar condicionado",
    ),
    (
        "secondary_water",
        "Setor secundário: Captação, tratamento e distribuição de água; saneamento, "
        "gestão de resíduos e despoluição",
    ),
    ("secondary_construction", "Setor secundário: Construção"),
    ("tertiary_trade", "Setor terciário: Comércio por grosso e a retalho"),
    ("tertiary_transport", "Setor terciário: Transportes e armazenagem"),
    ("tertiary_accommodation", "Setor terciário: Atividades de alojamento e restauração"),
    (
        "tertiary_media",
        "Setor terciário: Atividades de edição, difusão e produção e distribuição de conteúdos",
    ),
    (
        "tertiary_it",
        "Setor terciário: Telecomunicações, programação informática, consultoria, "
        "infraestruturas de computação e outras atividades dos serviços de informação",
    ),
    ("tertiary_finance", "Setor terciário: Atividades financeiras e de seguros"),
    ("tertiary_real_estate", "Setor terciário: Atividades imobiliárias"),
    (
        "tertiary_consulting",
        "Setor terciário: Atividades de consultoria, científicas, técnicas e similares",
    ),
    (
        "tertiary_admin_support",
        "Setor terciário: Atividades administrativas e dos serviços de apoio",
    ),
    (
        "tertiary_public_admin",
        "Setor terciário: Administração pública e defesa; segurança social obrigatória",
    ),
    ("tertiary_education", "Setor terciário: Educação"),
    ("tertiary_health", "Setor terciário: Atividades de saúde humana e ação social"),
    ("tertiary_arts", "Setor terciário: Atividades artísticas, desportivas e recreativas"),
    ("tertiary_other_services", "Setor terciário: Outras atividades de serviços"),
    (
        "tertiary_households",
        "Setor terciário: Atividades das famílias empregadoras de pessoal doméstico e "
        "atividades de produção de bens e serviços pelas famílias para uso próprio",
    ),
    (
        "tertiary_international",
        "Setor terciário: Atividades dos organismos internacionais e outras instituições "
        "extraterritoriais",
    ),
    ("other_activity", "Outra atividade"),
    ("not_applicable", "Não aplicável"),
]
