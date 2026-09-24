"""Settings control runtime books without deleting the editable document."""
from unittest.mock import patch
from plugins.ff8 import spellbook_integration as integration, gf_spellbooks as books


def test_settings_gate_preserves_books(tmp_path):
    document={'schemaVersion':1,'books':[{'gfId':0,'pages':[[{'magicId':1,'abilityId':None}]]}]}
    books.save(tmp_path,document)
    settings=integration.gameplay_settings
    with patch.object(integration,'_installed',False), \
         patch.object(settings,'save',return_value={}), \
         patch.object(settings,'initialize_project'), \
         patch.object(integration.formats,'kernel_rows'), \
         patch.object(integration.formats,'save_kernel'):
        # Capture installed wrappers inside the patch so no globals escape.
        integration.install()
        for enabled,single,shared in [(True,True,False),(False,True,False),(True,False,False),(True,True,True)]:
            settings.save({'gfSpellbooksEnabled':enabled,'singleGf':single,'sharedMagicInventory':shared},project_root=tmp_path)
            runtime=books.parse_runtime((tmp_path/books.RUNTIME_RELATIVE).read_bytes())
            assert bool(runtime['books'])==(enabled and single and not shared)
            assert books.load(tmp_path)==document
        with patch.object(settings,'load',return_value={'gfSpellbooksEnabled':False,'singleGf':True}), \
             patch.object(integration.paths,'PROJECT_ROOT',tmp_path):
            integration.formats.save_kernel(3,[{'id':0,'field':'__spellbook','value':[[{'magicId':2,'abilityId':None}]]}])
            assert books.load(tmp_path)['books'][0]['pages'][0][0]['magicId']==2
            assert books.parse_runtime((tmp_path/books.RUNTIME_RELATIVE).read_bytes())['books']==[]
