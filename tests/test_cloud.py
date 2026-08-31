import unittest

from sceneops.cloud import (
    GoogleTranscoderAdapter,
    MockOutputVerifier,
    TranscoderJobRequest,
)


class FakeTranscoderClient:
    def __init__(self):
        self.created = None

    def create_job(self, **kwargs):
        self.created = kwargs
        return {'name': kwargs['parent'] + '/jobs/job-1', **kwargs['job']}

    def get_job(self, **kwargs):
        return {'name': kwargs['name'], 'state': 'SUCCEEDED'}

    def list_jobs(self, **kwargs):
        return [{'name': kwargs['parent'] + '/jobs/job-1'}]


class CloudAdapterContractTests(unittest.TestCase):
    def test_official_transcoder_shape_is_mock_contract_tested(self):
        client = FakeTranscoderClient()
        adapter = GoogleTranscoderAdapter(client, lambda **values: values)
        request = TranscoderJobRequest(
            'project-demo',
            'us-central1',
            'gs://input/video.mov',
            'gs://output/job/',
            'preset/web-hd',
            {'pipeline': 'sceneops'},
        )
        created = adapter.create_job(request)
        self.assertEqual(
            client.created['parent'],
            'projects/project-demo/locations/us-central1',
        )
        self.assertEqual(created['template_id'], 'preset/web-hd')
        self.assertEqual(
            adapter.get_job('project-demo', 'us-central1', 'job-1')['state'],
            'SUCCEEDED',
        )
        self.assertEqual(len(adapter.list_jobs('project-demo', 'us-central1')), 1)

    def test_invalid_cloud_ownership_and_output_lookups_fail_closed(self):
        with self.assertRaises(ValueError):
            TranscoderJobRequest(
                '../other',
                'us-central1',
                'file://input',
                'gs://output/',
                'preset/web-hd',
                {},
            )
        verifier = MockOutputVerifier(
            {'gs://output/job/video.mp4': {'size_bytes': 10}}
        )
        self.assertEqual(
            verifier.metadata('project-demo', 'gs://output/job/video.mp4')[
                'size_bytes'
            ],
            10,
        )
        with self.assertRaises(ValueError):
            verifier.metadata('../other', 'gs://output/job/video.mp4')


if __name__ == '__main__':
    unittest.main()
