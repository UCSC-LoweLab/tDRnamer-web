// tDRresult.js

function drawMFE(divId, strSequence, strStructure)
{
    var container = new fornac.FornaContainer(divId, {'applyForce': false, 
        'layout': 'naview', 'initialSize': [500,500], 'labelInterval': 0});

    var options = {'structure': strStructure,
                'sequence': strSequence
    };

    container.addRNA(options.structure, options);
    container.setSize();
    container.changeColorScheme('sequence');
}
