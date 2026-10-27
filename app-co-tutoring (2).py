import streamlit as st
import pandas as pd
import numpy as np
import io

# -----------------------------------------------------------------------------
# CONFIGURAZIONE PAGINA & PREVENZIONE ERRORE TRADUZIONE GOOGLE
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Pegaso Co-Tutoring Matcher",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inserimento tag HTML per impedire a Google Traduttore di corrompere il DOM React
st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)

# Styling CSS personalizzato
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        color: #0A192F;
        font-weight: 700;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #334155;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# DATI DI PROVA PREDEFINITI
# -----------------------------------------------------------------------------
if 'tutors' not in st.session_state:
    st.session_state.tutors = pd.DataFrame([
        {'nome': 'Dr. Iadicicco', 'sede': 'Napoli', 'agency': 82, 'communion': 88, 'coscienziosita': 90, 'apertura': 85, 'skills': 'Bilancio, E-Portfolio', 'belbin_role': 'Azione', 'disponibile': True},
        {'nome': 'Dr. Macera', 'sede': 'Napoli', 'agency': 55, 'communion': 85, 'coscienziosita': 88, 'apertura': 90, 'skills': 'Diario, Inclusione', 'belbin_role': 'Sociale', 'disponibile': True},
        {'nome': 'Dr. Messina', 'sede': 'Napoli', 'agency': 60, 'communion': 92, 'coscienziosita': 85, 'apertura': 80, 'skills': 'E-Portfolio, Metodologie', 'belbin_role': 'Valutazione', 'disponibile': True},
        {'nome': 'Dr. Salis', 'sede': 'Napoli', 'agency': 78, 'communion': 80, 'coscienziosita': 92, 'apertura': 75, 'skills': 'Regia, Diario', 'belbin_role': 'Azione', 'disponibile': True},
        {'nome': 'Dr. Scialpi', 'sede': 'Napoli', 'agency': 50, 'communion': 90, 'coscienziosita': 86, 'apertura': 88, 'skills': 'Bilancio, Metodologie', 'belbin_role': 'Sociale', 'disponibile': True},
        {'nome': 'Dr. Scipilliti', 'sede': 'Roma', 'agency': 80, 'communion': 84, 'coscienziosita': 89, 'apertura': 82, 'skills': 'Inclusione, E-Portfolio', 'belbin_role': 'Azione', 'disponibile': True},
        {'nome': 'Dr. Rossi', 'sede': 'Roma', 'agency': 52, 'communion': 86, 'coscienziosita': 87, 'apertura': 85, 'skills': 'Bilancio, Diario', 'belbin_role': 'Sociale', 'disponibile': True},
    ])

if 'classrooms' not in st.session_state:
    st.session_state.classrooms = pd.DataFrame([
        {'nome_aula': 'Aula Magna A1', 'sede': 'Napoli', 'n_corsisti': 85, 'tipo': 'Triade'},
        {'nome_aula': 'Aula Laboratorio B2', 'sede': 'Napoli', 'n_corsisti': 48, 'tipo': 'Diade'},
        {'nome_aula': 'Aula Seminariale R1', 'sede': 'Roma', 'n_corsisti': 52, 'tipo': 'Diade'},
    ])

# -----------------------------------------------------------------------------
# FUNZIONI DELL'ALGORITMO
# -----------------------------------------------------------------------------
def compute_diad_score(t1, t2, w_skills, w_comm, w_agency):
    if t1['sede'] != t2['sede'] or not t1['disponibile'] or not t2['disponibile']:
        return -1e6

    skills1 = set([s.strip() for s in str(t1['skills']).split(',')])
    skills2 = set([s.strip() for s in str(t2['skills']).split(',')])
    skills_coverage = len(skills1.union(skills2)) / 5.0

    comm_fit = 1.0 - (abs(t1['communion'] - t2['communion']) / 100.0)
    cosc_fit = 1.0 - (abs(t1['coscienziosita'] - t2['coscienziosita']) / 100.0)
    comm_score = (comm_fit + cosc_fit) / 2.0

    a1, a2 = t1['agency'], t2['agency']
    if a1 > 75 and a2 > 75:
        agency_score = 0.2
    elif (a1 >= 60 and a2 < 60) or (a2 >= 60 and a1 < 60):
        agency_score = 1.0
    else:
        agency_score = 0.7

    total_weight = w_skills + w_comm + w_agency
    if total_weight == 0:
        total_weight = 1.0

    total_score = ((w_skills * skills_coverage) + (w_comm * comm_score) + (w_agency * agency_score)) / total_weight
    return round(total_score * 100, 2)

def compute_triad_score(t1, t2, t3, w_skills, w_comm, w_agency):
    d12 = compute_diad_score(t1, t2, w_skills, w_comm, w_agency)
    d23 = compute_diad_score(t2, t3, w_skills, w_comm, w_agency)
    d13 = compute_diad_score(t1, t3, w_skills, w_comm, w_agency)

    if min(d12, d23, d13) < 0:
        return -1e6

    avg_diad = (d12 + d23 + d13) / 3.0
    roles = {t1['belbin_role'], t2['belbin_role'], t3['belbin_role']}
    bonus = 15.0 if len(roles) == 3 else (5.0 if len(roles) == 2 else 0.0)
    return round(avg_diad + bonus, 2)

def run_matching(tutors_df, classrooms_df, w_skills, w_comm, w_agency):
    results = []
    available = tutors_df.copy()

    triad_rooms = classrooms_df[classrooms_df['tipo'] == 'Triade']
    for _, room in triad_rooms.iterrows():
        best_triad = None
        best_score = -1
        indices = available.index.tolist()

        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                for k in range(j + 1, len(indices)):
                    t1 = available.loc[indices[i]]
                    t2 = available.loc[indices[j]]
                    t3 = available.loc[indices[k]]

                    if t1['sede'] == room['sede']:
                        score = compute_triad_score(t1, t2, t3, w_skills, w_comm, w_agency)
                        if score > best_score:
                            best_score = score
                            best_triad = (t1, t2, t3, indices[i], indices[j], indices[k])

        if best_triad:
            t1, t2, t3, i1, i2, i3 = best_triad
            results.append({
                'Aula': room['nome_aula'],
                'Sede': room['sede'],
                'Tipo Configurazione': 'Triade',
                'N° Corsisti': room['n_corsisti'],
                'Componenti Team Abbinato': f"{t1['nome']} ({t1['belbin_role']}), {t2['nome']} ({t2['belbin_role']}), {t3['nome']} ({t3['belbin_role']})",
                'Punteggio Matching (0-100)': best_score
            })
            available = available.drop([i1, i2, i3])

    diad_rooms = classrooms_df[classrooms_df['tipo'] == 'Diade']
    for _, room in diad_rooms.iterrows():
        best_diad = None
        best_score = -1
        indices = available.index.tolist()

        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                t1 = available.loc[indices[i]]
                t2 = available.loc[indices[j]]

                if t1['sede'] == room['sede']:
                    score = compute_diad_score(t1, t2, w_skills, w_comm, w_agency)
                    if score > best_score:
                        best_score = score
                        best_diad = (t1, t2, indices[i], indices[j])

        if best_diad:
            t1, t2, i1, i2 = best_diad
            results.append({
                'Aula': room['nome_aula'],
                'Sede': room['sede'],
                'Tipo Configurazione': 'Diade',
                'N° Corsisti': room['n_corsisti'],
                'Componenti Team Abbinato': f"{t1['nome']} (Agency:{t1['agency']}), {t2['nome']} (Agency:{t2['agency']})",
                'Punteggio Matching (0-100)': best_score
            })
            available = available.drop([i1, i2])

    return pd.DataFrame(results)

# -----------------------------------------------------------------------------
# MENU DI NAVIGAZIONE
# -----------------------------------------------------------------------------
st.sidebar.title("Modello Pegaso")
st.sidebar.markdown("**Co-Tutoraggio & Regia d'Aula**")

menu = st.sidebar.radio(
    "Seleziona Modulo:",
    [
        "⚡ Engine di Matching Regionale",
        "📝 Profilazione Tutor (QP-CoT)",
        "📊 Gestione Dati (Excel/CSV)",
        "📜 Generatore Patto di Corresponsabilità",
        "📖 Quadro Scientifico (Parte Quinta)"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("📌 **Ateneo Pegaso** - Percorsi Abilitanti D.P.C.M. 4 agosto 2023

Sviluppato per il Gruppo 7")

if menu == "⚡ Engine di Matching Regionale":
    st.markdown('<div class="main-header">⚡ Engine di Matching per Diadi e Triadi</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Algoritmo di ottimizzazione vincolata fondato sui criteri di complementarità della Parte Quinta</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("⚙️ Parametri Algoritmo")
        w_skills = st.slider("Peso Complementarità Competenze", 0.0, 1.0, 0.35, 0.05)
        w_comm = st.slider("Peso Omofilia Communion/Coscienziosità", 0.0, 1.0, 0.30, 0.05)
        w_agency = st.slider("Peso Complementarità Agency (Regia)", 0.0, 1.0, 0.35, 0.05)

        filter_sede = st.selectbox("Filtra Sede Regionale:", ["Tutte"] + list(st.session_state.tutors['sede'].unique()))

        if filter_sede != "Tutte":
            tutors_filtered = st.session_state.tutors[st.session_state.tutors['sede'] == filter_sede]
            classrooms_filtered = st.session_state.classrooms[st.session_state.classrooms['sede'] == filter_sede]
        else:
            tutors_filtered = st.session_state.tutors
            classrooms_filtered = st.session_state.classrooms

        btn_run = st.button("🚀 Calcola Abbinamenti Ottimali", use_container_width=True, type="primary")

    with col2:
        st.subheader("📋 Elenco Aule e Co-Tutor Disponibili")
        tab_a, tab_b = st.tabs(["Docenti Tutor Registrati", "Aule Regionali"])
        with tab_a:
            st.dataframe(tutors_filtered[['nome', 'sede', 'agency', 'communion', 'belbin_role', 'skills']], use_container_width=True)
        with tab_b:
            st.dataframe(classrooms_filtered, use_container_width=True)

    if btn_run:
        st.markdown("---")
        st.subheader("🎯 Risultati dell'Elaborazione Algoritmica")
        res_df = run_matching(tutors_filtered, classrooms_filtered, w_skills, w_comm, w_agency)

        if not res_df.empty:
            st.dataframe(res_df, use_container_width=True)

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                res_df.to_excel(writer, index=False, sheet_name='Abbinamenti_Pegaso')

            st.download_button(
                label="📥 Scarica Report Abbinamenti in Excel",
                data=buffer.getvalue(),
                file_name="report_abbinamenti_cotutor_pegaso.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("Nessun abbinamento possibile con i filtri attuali.")

elif menu == "📝 Profilazione Tutor (QP-CoT)":
    st.markdown('<div class="main-header">📝 Questionario di Profilazione (QP-CoT)</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Compila i 15 quesiti psicometrici su scala Likert (1-5)</div>', unsafe_allow_html=True)

    with st.form("form_qp_cot"):
        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome e Cognome Docente:")
            sede = st.selectbox("Sede d'Afferenza:", ["Napoli", "Roma", "Milano", "Bari", "Palermo"])
        with c2:
            skills = st.multiselect(
                "Competenze Laboratoriali Specifiche:",
                ["Bilancio Competenze", "Diario di Bordo", "E-Portfolio", "Inclusione/UDL", "Regia d'Aula", "Metodologie Attive"],
                default=["Bilancio Competenze", "E-Portfolio"]
            )

        st.markdown("---")
        st.subheader("Istruzioni: indica il tuo grado di accordo (1 = Minimo, 5 = Massimo)")

        q1 = st.slider("1. Nelle situazioni d'aula prendo con naturalezza la parola in plenaria per guidare la discussione.", 1, 5, 4)
        q2 = st.slider("2. Cedo volentieri la conduzione principale al collega affiancandolo in modo discreto.", 1, 5, 4)
        q3 = st.slider("3. Nei momenti di esitazione intervengo con decisione per ripristinare la rotta.", 1, 5, 3)
        q4 = st.slider("4. Considero fondamentale pianificare in anticipo ogni dettaglio insieme al collega.", 1, 5, 5)
        q5 = st.slider("5. Mantengo un contatto visivo costante con il co-tutor per inviare segnali di supporto empatico.", 1, 5, 4)
        q6 = st.slider("6. Nel debriefing condivido apertamente le mie incertezze o gli errori commessi.", 1, 5, 4)
        q7 = st.slider("7. Considero i 60 minuti di co-planning un vincolo non negoziabile.", 1, 5, 5)
        q8 = st.slider("8. Monitoro costantemente l'orologio per garantire il rispetto dei tempi assegnati.", 1, 5, 4)
        q9 = st.slider("9. Compilo le schede di debriefing con precisione entro le 48 ore successive.", 1, 5, 5)
        q10 = st.slider("10. Se la classe ha un bisogno emergente, riadatto al volo la Co-Roadmap.", 1, 5, 4)
        q11 = st.slider("11. Amo sperimentare strategie articolate come lo Station Teaching o gruppi alternativi.", 1, 5, 4)
        q12 = st.slider("12. Esprimo la mia massima efficacia coordinando la plenaria e facendo le sintesi.", 1, 5, 4)
        q13 = st.slider("13. Preferisco circolare tra i banchi e facilitare i sottogruppi di lavoro.", 1, 5, 3)
        q14 = st.slider("14. Trovo stimolante osservare il gruppo e raccogliere dati con il framework OMF.", 1, 5, 3)
        q15 = st.slider("15. La presenza del collega in aula è un'occasione speculare di crescita professionale.", 1, 5, 5)

        submit = st.form_submit_button("💾 Salva Profilo e Calcola Vettore")

    if submit and nome:
        agency = int(((q1 + q3) / 2.0 * 20) - (q2 * 5) + 25)
        agency = max(10, min(99, agency))
        communion = int(((q4 + q5 + q6) / 3.0) * 20)
        coscienziosita = int(((q7 + q8 + q9) / 3.0) * 20)
        apertura = int(((q10 + q11) / 2.0) * 20)

        belbin_scores = {'Azione': q12, 'Sociale': q13, 'Valutazione': q14}
        belbin_role = max(belbin_scores, key=belbin_scores.get)

        new_tutor = {
            'nome': nome,
            'sede': sede,
            'agency': agency,
            'communion': communion,
            'coscienziosita': coscienziosita,
            'apertura': apertura,
            'skills': ", ".join(skills),
            'belbin_role': belbin_role,
            'disponibile': True
        }

        st.session_state.tutors = pd.concat([st.session_state.tutors, pd.DataFrame([new_tutor])], ignore_index=True)
        st.success(f"✅ Profilo del docente **{nome}** registrato con successo!")

elif menu == "📊 Gestione Dati (Excel/CSV)":
    st.markdown('<div class="main-header">📊 Importazione ed Esportazione Dati</div>', unsafe_allow_html=True)

    col_up1, col_up2 = st.columns(2)

    with col_up1:
        st.subheader("📤 Carica File Co-Tutor")
        file_tutors = st.file_uploader("Seleziona file Excel/CSV Co-Tutor", type=['xlsx', 'csv'])
        if file_tutors:
            try:
                df_u = pd.read_csv(file_tutors) if file_tutors.name.endswith('.csv') else pd.read_excel(file_tutors)
                st.session_state.tutors = df_u
                st.success("Elenco Co-Tutor aggiornato!")
            except Exception as e:
                st.error(f"Errore: {e}")

    with col_up2:
        st.subheader("📤 Carica File Aule Regionali")
        file_rooms = st.file_uploader("Seleziona file Excel/CSV Aule", type=['xlsx', 'csv'])
        if file_rooms:
            try:
                df_r = pd.read_csv(file_rooms) if file_rooms.name.endswith('.csv') else pd.read_excel(file_rooms)
                st.session_state.classrooms = df_r
                st.success("Elenco Aule aggiornato!")
            except Exception as e:
                st.error(f"Errore: {e}")

elif menu == "📜 Generatore Patto di Corresponsabilità":
    st.markdown('<div class="main-header">📜 Patto di Corresponsabilità Professionale</div>', unsafe_allow_html=True)

    t_list = st.session_state.tutors['nome'].tolist()
    c1, c2 = st.columns(2)
    with c1:
        tutor1_sel = st.selectbox("Seleziona Primo Co-Tutor (Tutor A):", t_list, index=0 if len(t_list)>0 else 0)
    with c2:
        tutor2_sel = st.selectbox("Seleziona Secondo Co-Tutor (Tutor B):", t_list, index=1 if len(t_list)>1 else 0)

    if tutor1_sel and tutor2_sel and tutor1_sel != tutor2_sel:
        patto_text = f"""=================================================================================
             PATTO DI CORRESPONSABILITÀ PROFESSIONALE (MODELLO PEGASO)
=================================================================================

Il/La sottoscritto/a {tutor1_sel} e il/la sottoscritto/a {tutor2_sel},
in qualità di Co-Tutor abbinati per i laboratori di tirocinio indiretto (D.P.C.M. 4 agosto 2023),

SOTTOSCRIVONO E SI IMPEGNANO A RISPETTARE QUANTO SEGUE:

1. PARITÀ DI STATUS PROFESSIONALE (Parity of Professional Status):
   Entrambi i Co-Tutor operano dinanzi alla classe con la medesima autorevolezza,
   superando ogni gerarchia. La conduzione dell'aula è condivisa in regime di pari dignità.

2. TEMPI PROTETTI DI CO-PROGETTAZIONE E DEBRIEFING:
   - Garanzia di svolgimento dei 60 MINUTI PROTETTI di Co-Planning preparatorio (Scheda S-CoP);
   - Garanzia di svolgimento dei 45 MINUTI PROTETTI di Co-Debriefing riflessivo entro 48 ore (Scheda S-Deb).

3. REGIA D'AULA E MODELLAMENTO (Modeling):
   - Alternanza fluida della voce durante le 6 ore in presenza;
   - Applicazione trasparente delle 5 configurazioni d'aula (Cook & Friend);
   - Sostegno empatico reciproco dinanzi ai corsisti per modellare l'inclusione.

Data: ____________________

Firma Tutor A: ___________________________    Firma Tutor B: ___________________________
"""
        st.text_area("Testo del Patto Generato:", patto_text, height=300)
        st.download_button("📥 Scarica Patto (.txt)", patto_text, file_name="patto_corresponsabilita_pegaso.txt")

elif menu == "📖 Quadro Scientifico (Parte Quinta)":
    st.markdown('<div class="main-header">📖 Parte Quinta — Fondamenti Scientifici e Psicometrici</div>', unsafe_allow_html=True)
    st.markdown("""
    ### La complementarità relazionale nel co-tutoraggio
    
    Il modello di abbinamento sviluppato dall'Ateneo Pegaso per i percorsi abilitanti integra la letteratura scientifica internazionale:
    
    * **Big Five / OCEAN** (*Goldberg, McCrae & Costa, Rhodes*): misura Coscienziosità e Stabilità Emotiva per il rispetto dei tempi protetti e l'eliminazione dell'ansia da prestazione.
    * **Circomplesso Interpersonale** (*Leary, Wiggins, Kiesler, Sadler*): applica l'**omofilia sulla Communion** (calore e cooperazione condivisa) e la **complementarità sull'Agency** (equilibrio tra guida assertiva e flessibilità relazionale).
    * **Ruoli di Team di Belbin**: garantisce la saturazione dei 3 ruoli d'aula (Azione, Sociale, Valutazione) nelle triadi operanti su aule complesse.
    """)
    st.info("Ispirato ai principi del D.P.C.M. 4 agosto 2023 per l'inclusione e la parità di status nei percorsi abilitanti.")
