import { Connection } from '@solana/web3.js';

async function testTokenDiscoveryMethods() {
  console.log('🔍 Testing token discovery methods that are failing...\n');
  
  const connection = new Connection('https://api.mainnet-beta.solana.com', {
    commitment: 'processed',
    confirmTransactionInitialTimeout: 5000
  });
  
  try {
    console.log('📊 Testing getSlot...');
    const slot = await connection.getSlot();
    console.log(`✅ Current slot: ${slot}`);
    
    console.log('\n📦 Testing getBlock for recent slots...');
    const recentSlots = Array.from({ length: 3 }, (_, i) => slot - i);
    
    for (const slotNumber of recentSlots) {
      console.log(`  Testing slot ${slotNumber}...`);
      try {
        const startTime = Date.now();
        const block = await connection.getBlock(slotNumber, {
          commitment: 'confirmed',
          maxSupportedTransactionVersion: 0
        });
        
        if (block) {
          console.log(`  ✅ Block ${slotNumber}: ${block.transactions?.length || 0} transactions, ${Date.now() - startTime}ms`);
        } else {
          console.log(`  ⚠️ Block ${slotNumber}: No data`);
        }
      } catch (error) {
        console.log(`  ❌ Block ${slotNumber}: ${error.message}`);
      }
    }
    
    console.log('\n🔄 Testing alternative: getSignaturesForAddress...');
    try {
      const TOKEN_PROGRAM_ID = 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA';
      const signatures = await connection.getSignaturesForAddress(
        new (await import('@solana/web3.js')).PublicKey(TOKEN_PROGRAM_ID),
        { limit: 5 }
      );
      console.log(`✅ getSignaturesForAddress: ${signatures.length} signatures found`);
    } catch (error) {
      console.log(`❌ getSignaturesForAddress: ${error.message}`);
    }
    
  } catch (error) {
    console.log(`❌ Critical error: ${error.message}`);
  }
}

testTokenDiscoveryMethods().catch(console.error);
