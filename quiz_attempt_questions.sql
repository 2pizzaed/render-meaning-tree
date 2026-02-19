-- Вопросы в попытках теста с оценками и тремя уровнями категорий
--
-- Иерархия категорий (от непосредственной к корневой):
--   qc1 — непосредственная категория вопроса
--   qc2 — родительская категория (parent)
--   qc3 — категория-прародитель (grandparent)
--
-- Для Moodle < 4.0: категория берётся напрямую из mdl_question.category
-- Для Moodle 4.0+: см. альтернативный вариант в конце файла

SELECT
    u.id                        AS userid,
    u.lastname,
    u.firstname,

    qa.quiz                     AS quizid,
    qa.id                       AS attemptid,
    qa.attempt                  AS attemptnumber,

    q.id                        AS questionid,
    q.name                      AS questionname,

    qc1.id                      AS category_level1_id,
    qc1.name                    AS category_level1_name,

    qc2.id                      AS category_level2_id,
    qc2.name                    AS category_level2_name,

    qc3.id                      AS category_level3_id,
    qc3.name                    AS category_level3_name,

    qa_q.maxmark                AS question_max_mark,

    qas.fraction * qa_q.maxmark AS question_mark_obtained

FROM mdl_quiz_attempts qa

JOIN mdl_user u
    ON u.id = qa.userid

JOIN mdl_question_attempts qa_q
    ON qa_q.questionusageid = qa.uniqueid

JOIN mdl_question q
    ON q.id = qa_q.questionid

-- Уровень 1: непосредственная категория вопроса
JOIN mdl_question_categories qc1
    ON qc1.id = q.category

-- Уровень 2: родительская категория (NULL, если qc1 — корневая)
LEFT JOIN mdl_question_categories qc2
    ON qc1.parent <> 0
   AND qc2.id = qc1.parent

-- Уровень 3: категория-прародитель (NULL, если qc2 отсутствует или корневая)
LEFT JOIN mdl_question_categories qc3
    ON qc2.parent <> 0
   AND qc3.id = qc2.parent

JOIN mdl_question_attempt_steps qas
    ON qas.questionattemptid = qa_q.id
   AND qas.sequencenumber = (
        SELECT MAX(qas2.sequencenumber)
          FROM mdl_question_attempt_steps qas2
         WHERE qas2.questionattemptid = qa_q.id
       )

WHERE qa.quiz  = :quizid
  AND qa.state = 'finished'

ORDER BY
    u.lastname,
    u.firstname,
    qa.attempt,
    qa_q.slot;


-- ============================================================================
-- Альтернативный вариант для Moodle 4.0+
-- ============================================================================
-- В Moodle 4.0 категория вопроса определяется через промежуточные таблицы:
--   mdl_question
--     → mdl_question_versions   (по questionid)
--     → mdl_question_bank_entries (по questionbankentryid)
--     → mdl_question_categories   (по questioncategoryid)
--
-- Замените блок JOIN-ов для категорий на следующий:
--
-- JOIN mdl_question_versions qv
--     ON qv.questionid = q.id
--
-- JOIN mdl_question_bank_entries qbe
--     ON qbe.id = qv.questionbankentryid
--
-- JOIN mdl_question_categories qc1
--     ON qc1.id = qbe.questioncategoryid
--
-- LEFT JOIN mdl_question_categories qc2
--     ON qc1.parent <> 0
--    AND qc2.id = qc1.parent
--
-- LEFT JOIN mdl_question_categories qc3
--     ON qc2.parent <> 0
--    AND qc3.id = qc2.parent
-- ============================================================================
