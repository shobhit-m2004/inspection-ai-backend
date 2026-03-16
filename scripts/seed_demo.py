from app.db.session import SessionLocal
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType
from app.services.analysis_service import analysis_service


def run_seed() -> None:
    db = SessionLocal()
    try:
        sop = Document(
            type=DocumentType.SOP,
            original_filename='sample_sop.txt',
            storage_path='samples/sample_sop.txt',
            raw_text=open('samples/sample_sop.txt', encoding='utf-8').read(),
            extracted_json={
                'rules': [
                    {
                        'rule_id': 'R1',
                        'section': 'Mixing',
                        'parameter': 'temperature',
                        'aliases': ['temp', 'mix temp'],
                        'rule_type': 'range',
                        'expected_action': 'maintain',
                        'min_value': 23,
                        'max_value': 27,
                        'target_value': 25,
                        'unit': 'C',
                        'frequency': None,
                        'mandatory': True,
                        'condition': None,
                        'sequence_before': None,
                        'source_text': 'Temperature should be maintained at 25 +/- 2 C',
                    }
                ]
            },
            approved_json={
                'rules': [
                    {
                        'rule_id': 'R1',
                        'section': 'Mixing',
                        'parameter': 'temperature',
                        'aliases': ['temp', 'mix temp'],
                        'rule_type': 'range',
                        'expected_action': 'maintain',
                        'min_value': 23,
                        'max_value': 27,
                        'target_value': 25,
                        'unit': 'C',
                        'frequency': None,
                        'mandatory': True,
                        'condition': None,
                        'sequence_before': None,
                        'source_text': 'Temperature should be maintained at 25 +/- 2 C',
                    }
                ]
            },
            status=DocumentStatus.APPROVED,
        )
        log = Document(
            type=DocumentType.LOG,
            original_filename='sample_log.txt',
            storage_path='samples/sample_log.txt',
            raw_text=open('samples/sample_log.txt', encoding='utf-8').read(),
            extracted_json={
                'observations': [
                    {
                        'observation_id': 'O1',
                        'timestamp': '2026-03-16T10:00:00',
                        'parameter': 'temperature',
                        'aliases_detected': ['temp'],
                        'normalized_value': 28,
                        'unit': 'C',
                        'status': 'recorded',
                        'raw_text': 'Temp observed: 28 C',
                        'source_location': 'page_1',
                        'confidence': 0.94,
                    }
                ]
            },
            approved_json={
                'observations': [
                    {
                        'observation_id': 'O1',
                        'timestamp': '2026-03-16T10:00:00',
                        'parameter': 'temperature',
                        'aliases_detected': ['temp'],
                        'normalized_value': 28,
                        'unit': 'C',
                        'status': 'recorded',
                        'raw_text': 'Temp observed: 28 C',
                        'source_location': 'page_1',
                        'confidence': 0.94,
                    }
                ]
            },
            status=DocumentStatus.APPROVED,
        )

        db.add(sop)
        db.add(log)
        db.commit()
        db.refresh(sop)
        db.refresh(log)

        analysis_service.run_analysis(db, sop.id, log.id)
        print('Seed complete: approved SOP + LOG + analysis inserted.')
    finally:
        db.close()


if __name__ == '__main__':
    run_seed()
